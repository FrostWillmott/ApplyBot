"""Application service for job applications."""

import asyncio
import logging
from datetime import datetime

from app.core.storage import async_session
from app.models.application import ApplicationHistory
from app.schemas.apply import ApplyRequest, ApplyResponse, BulkApplyRequest
from app.services.hh_client import HHClient
from app.services.llm.base import LLMProvider
from app.utils.filters import ApplicationFilter
from app.utils.validators import validate_application_request

logger = logging.getLogger(__name__)


class ApplicationService:
    """Core service for handling job applications."""

    def __init__(self, hh_client: HHClient, llm_provider: LLMProvider):
        self.hh_client = hh_client
        self.llm_provider = llm_provider

    async def apply_to_single_vacancy(
            self,
            vacancy_id: str,
            request: ApplyRequest,
            user_id: str | None = None,
            use_cover_letter: bool = True
    ) -> ApplyResponse:
        """Apply to a single vacancy."""
        validation_result = await validate_application_request(request)
        if not validation_result.is_valid:
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                error_detail=f"Invalid request: {validation_result.error}"
            )

        try:
            if await self._has_already_applied(vacancy_id, request.resume_id):
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    error_detail="Already applied to this vacancy"
                )

            vacancy = await self.hh_client.get_vacancy_details(vacancy_id)
            can_apply, reason = await self._can_apply_to_vacancy(vacancy)
            if not can_apply:
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    vacancy_title=vacancy.get("name"),
                    error_detail=reason
                )

            application_content = await self._generate_application_content(
                vacancy, request, use_cover_letter=use_cover_letter
            )

            hh_response = await self.hh_client.apply(
                vacancy_id=vacancy_id,
                resume_id=request.resume_id,
                cover_letter=application_content.get("cover_letter"),
                answers=application_content.get("answers")
            )

            await self._record_application(
                vacancy_id=vacancy_id,
                request=request,
                response=hh_response,
                user_id=user_id
            )

            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="success",
                vacancy_title=vacancy.get("name"),
                cover_letter=application_content.get("cover_letter"),
                hh_response=hh_response
            )

        except Exception as e:
            logger.error(f"Application failed for vacancy {vacancy_id}: {e}")
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                vacancy_title=vacancy.get("name", "Unknown"),
                error_detail=str(e)
            )

    async def bulk_apply(
            self,
            request: BulkApplyRequest,
            max_applications: int = 20,
            user_id: str | None = None,
            cancel_check: callable = None
    ) -> list[ApplyResponse]:
        """Apply to multiple vacancies based on search criteria."""
        logger.info(f"Starting bulk application for: {request.position}")

        filter_engine = ApplicationFilter(request)
        results = []
        applied_count = 0

        try:
            logger.info("Fetching previously applied vacancies from HH.ru...")
            already_applied_ids = await self.hh_client.get_applied_vacancy_ids()
            logger.info(f"User has {len(already_applied_ids)} existing applications on HH.ru")

            vacancies = await self._search_vacancies_for_bulk(request, max_applications)

            if not vacancies:
                logger.warning(f"No vacancies found for: {request.position}")
                return []

            skipped_already_applied = 0
            for vacancy in vacancies:
                # Check for cancellation
                if cancel_check and cancel_check():
                    logger.info("Bulk application cancelled by user")
                    break

                if applied_count >= max_applications:
                    break

                vacancy_id = str(vacancy.get("id", ""))

                if vacancy_id in already_applied_ids:
                    skipped_already_applied += 1
                    results.append(ApplyResponse(
                        vacancy_id=vacancy_id,
                        status="skipped",
                        vacancy_title=vacancy.get("name"),
                        error_detail="Already applied (HH.ru)"
                    ))
                    continue

                should_apply, filter_reason = filter_engine.should_apply(vacancy)
                if not should_apply:
                    results.append(ApplyResponse(
                        vacancy_id=vacancy_id,
                        status="skipped",
                        vacancy_title=vacancy.get("name"),
                        error_detail=f"Filtered: {filter_reason}"
                    ))
                    continue

                use_cover_letter = getattr(request, 'use_cover_letter', True)
                response = await self.apply_to_single_vacancy(
                    vacancy_id, request, user_id, use_cover_letter=use_cover_letter
                )
                results.append(response)

                if response.status == "success":
                    applied_count += 1
                    await asyncio.sleep(3)

            logger.info(
                f"Bulk application completed: {applied_count} sent, "
                f"{skipped_already_applied} skipped (already applied)"
            )
            return results

        except Exception as e:
            logger.error(f"Bulk application failed: {e}")
            raise

    async def _search_vacancies_for_bulk(
            self,
            request: BulkApplyRequest,
            max_applications: int
    ) -> list[dict]:
        """Search and collect vacancies with API-level filtering."""
        all_vacancies = []
        page = 0

        schedule = None
        if request.remote_only:
            schedule = "remote"
        elif request.preferred_schedule and len(request.preferred_schedule) == 1:
            schedule = request.preferred_schedule[0]

        employment = None
        if request.employment_types and len(request.employment_types) == 1:
            employment = request.employment_types[0]

        logger.info(
            f"Searching vacancies with API filters: "
            f"text={request.position}, experience={request.experience_level}, "
            f"schedule={schedule}, salary={request.salary_min}"
        )

        while len(all_vacancies) < max_applications * 2:
            search_results = await self.hh_client.search_vacancies(
                text=request.position,
                experience=request.experience_level,
                schedule=schedule,
                employment=employment,
                salary=request.salary_min,
                only_with_salary=bool(request.salary_min),
                page=page,
                per_page=100
            )

            page_vacancies = search_results.get("items", [])
            if not page_vacancies:
                break

            all_vacancies.extend(page_vacancies)
            page += 1

            total_found = search_results.get("found", 0)
            logger.info(f"Page {page}: got {len(page_vacancies)} vacancies (total found: {total_found})")

            if page >= 3:
                break

        logger.info(f"Collected {len(all_vacancies)} pre-filtered vacancies from API")
        return all_vacancies

    async def _generate_application_content(
            self,
            vacancy: dict,
            request: ApplyRequest,
            use_cover_letter: bool = True
    ) -> dict:
        """Generate cover letter and answer screening questions."""
        result = {"cover_letter": None}

        if use_cover_letter:
            user_profile = await self._build_user_profile(request)
            cover_letter = await self.llm_provider.generate_cover_letter(
                vacancy, user_profile
            )
            result["cover_letter"] = cover_letter

            questions = await self.hh_client.get_vacancy_questions(vacancy["id"])
            if questions:
                logger.info(f"Vacancy {vacancy.get('id')} has {len(questions)} screening questions")
                answers = await self.llm_provider.answer_screening_questions(
                    questions, vacancy, user_profile
                )
                if answers:
                    logger.info(f"Generated {len(answers)} answers for screening questions")
                    result["answers"] = answers
        else:
            logger.info(f"Skipping cover letter generation for vacancy {vacancy.get('id')}")

        return result

    async def _build_user_profile(self, request: ApplyRequest) -> dict:
        """Build user profile dictionary for LLM."""
        resume_details = await self.hh_client.get_resume_details(request.resume_id)

        experience = resume_details.get("experience", [])
        skills = resume_details.get("skill_set", [])
        education = resume_details.get("education", {}).get("items", [])

        formatted_experience = ""
        for exp in experience:
            company = exp.get("company", "")
            position = exp.get("position", "")
            start_date = exp.get("start", "")
            end_date = exp.get("end", "") or "Present"
            description = exp.get("description", "")
            formatted_experience += f"{company}, {position}, {start_date} - {end_date}: {description}\n"

        if skills:
            if skills and isinstance(skills[0], dict):
                formatted_skills = ", ".join([skill.get("name", "") for skill in skills])
            else:
                formatted_skills = ", ".join([str(skill) for skill in skills])
        else:
            formatted_skills = request.skills

        return {
            "experience": formatted_experience or request.experience,
            "skills": formatted_skills or request.skills,
            "resume": resume_details.get("description", "") or request.resume,
            "education": education,
            "position": resume_details.get("title", "") or request.position,
        }

    async def _can_apply_to_vacancy(self, vacancy: dict) -> tuple[bool, str]:
        """Check if we can apply to a vacancy."""
        vacancy_id = vacancy.get("id", "unknown")
        vacancy_name = vacancy.get("name", "unknown")
        
        if vacancy.get("archived", False):
            logger.info(f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - archived")
            return False, "Vacancy is archived"

        relations = vacancy.get("relations", [])
        if "got_response" in relations or "response" in relations:
            logger.info(f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - already applied")
            return False, "Already applied to this vacancy"

        logger.info(f"Vacancy {vacancy_id} ({vacancy_name}): CAN APPLY")
        return True, ""

    async def _has_already_applied(
            self,
            vacancy_id: str,
            resume_id: str
    ) -> bool:
        """Check if we've already applied to this vacancy."""
        async with async_session() as session:
            from sqlalchemy import select
            from app.models.application import ApplicationHistory

            # Query the application history
            query = select(ApplicationHistory).where(
                ApplicationHistory.vacancy_id == vacancy_id,
                ApplicationHistory.resume_id == resume_id
            )

            result = await session.execute(query)
            application = result.scalar_one_or_none()

            return application is not None

    async def _record_application(
            self,
            vacancy_id: str,
            request: ApplyRequest,
            response: dict,
            user_id: str | None = None
    ):
        """Record application in database for tracking."""
        async with async_session() as session:
            application = ApplicationHistory(
                vacancy_id=vacancy_id,
                resume_id=request.resume_id,
                user_id=user_id,
                applied_at=datetime.utcnow(),
                hh_response=response
            )
            session.add(application)
            await session.commit()


# Factory function for dependency injection
def create_application_service(
        hh_client: HHClient,
        llm_provider: LLMProvider
) -> ApplicationService:
    """Factory function to create ApplicationService with dependencies."""
    return ApplicationService(hh_client, llm_provider)
