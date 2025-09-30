"""Main application business logic for job applications.

This file contains:
- Application workflow orchestration
- Business rules and validation
- Integration between HH.ru API and LLM services
- Application filtering and processing logic
"""

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
    """Core service for handling job applications.

    This service orchestrates the entire application process:
    1. Vacancy search and filtering
    2. Application content generation
    3. Submission to HH.ru
    4. Result tracking and analytics
    """

    def __init__(self, hh_client: HHClient, llm_provider: LLMProvider):
        self.hh_client = hh_client
        self.llm_provider = llm_provider

    async def apply_to_single_vacancy(
            self,
            vacancy_id: str,
            request: ApplyRequest,
            user_id: str | None = None
    ) -> ApplyResponse:
        """Apply to a single vacancy.

        Business Logic:
        1. Validate request and check if already applied
        2. Fetch vacancy details and questions
        3. Generate personalized application content
        4. Submit application to HH.ru
        5. Record application in database
        """
        # Validate request
        validation_result = await validate_application_request(request)
        if not validation_result.is_valid:
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                error_detail=f"Invalid request: {validation_result.error}"
            )

        try:
            # Check if already applied
            if await self._has_already_applied(vacancy_id, request.resume_id):
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    error_detail="Already applied to this vacancy"
                )

            # Fetch vacancy details
            vacancy = await self.hh_client.get_vacancy_details(vacancy_id)

            # Business rule: Check if we can apply
            can_apply, reason = await self._can_apply_to_vacancy(vacancy)
            if not can_apply:
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    vacancy_title=vacancy.get("name"),
                    error_detail=reason
                )

            # Generate application content
            application_content = await self._generate_application_content(
                vacancy, request
            )

            # Submit to HH.ru
            hh_response = await self.hh_client.apply(
                vacancy_id=vacancy_id,
                resume_id=request.resume_id,
                cover_letter=application_content["cover_letter"],
                answers=application_content.get("answers")
            )

            # Record successful application
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
                cover_letter=application_content["cover_letter"],
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
            user_id: str | None = None
    ) -> list[ApplyResponse]:
        """Apply to multiple vacancies based on search criteria.

        Business Logic:
        1. Search for matching vacancies
        2. Apply filters to narrow down candidates
        3. Process applications with rate limiting
        4. Track progress and handle errors gracefully
        """
        logger.info(f"Starting bulk application for: {request.position}")

        # Initialize filter
        filter_engine = ApplicationFilter(request)
        results = []
        applied_count = 0

        try:
            # Search for vacancies
            vacancies = await self._search_vacancies_for_bulk(request, max_applications)

            if not vacancies:
                logger.warning(f"No vacancies found for: {request.position}")
                return []

            # Process each vacancy
            for vacancy in vacancies:
                if applied_count >= max_applications:
                    break

                # Apply business filters
                should_apply, filter_reason = filter_engine.should_apply(vacancy)
                if not should_apply:
                    results.append(ApplyResponse(
                        vacancy_id=vacancy["id"],
                        status="skipped",
                        vacancy_title=vacancy.get("name"),
                        error_detail=f"Filtered: {filter_reason}"
                    ))
                    continue

                # Apply to vacancy
                response = await self.apply_to_single_vacancy(
                    vacancy["id"], request, user_id
                )
                results.append(response)

                if response.status == "success":
                    applied_count += 1
                    # Rate limiting - be respectful to HH.ru
                    await asyncio.sleep(2)

            logger.info(f"Bulk application completed: {applied_count} applications sent")
            return results

        except Exception as e:
            logger.error(f"Bulk application failed: {e}")
            raise

    async def get_application_analytics(
            self,
            user_id: str,
            days: int = 30
    ) -> dict:
        """Get application statistics and analytics.

        Business Logic:
        - Calculate success rates
        - Track application trends
        - Identify best-performing strategies
        """
        async with async_session() as session:
            # Query application history
            # Implementation depends on your database structure
            pass

    # Private methods for internal business logic

    async def _search_vacancies_for_bulk(
            self,
            request: BulkApplyRequest,
            max_applications: int
    ) -> list[dict]:
        """Search and collect vacancies for bulk processing."""
        all_vacancies = []
        page = 0

        while len(all_vacancies) < max_applications * 3:  # Get extra for filtering
            search_results = await self.hh_client.search_vacancies(
                text=request.position,
                page=page,
                per_page=100
            )

            page_vacancies = search_results.get("items", [])
            if not page_vacancies:
                break

            all_vacancies.extend(page_vacancies)
            page += 1

            if page >= 5:  # Limit search depth
                break

        return all_vacancies

    async def _generate_application_content(
            self,
            vacancy: dict,
            request: ApplyRequest
    ) -> dict:
        """Generate cover letter and answer screening questions."""
        user_profile = await self._build_user_profile(request)

        # Generate cover letter
        cover_letter = await self.llm_provider.generate_cover_letter(
            vacancy, user_profile
        )

        result = {"cover_letter": cover_letter}

        # Handle screening questions if present
        questions = await self.hh_client.get_vacancy_questions(vacancy["id"])
        if questions:
            answers = await self.llm_provider.answer_screening_questions(
                questions, vacancy, user_profile
            )
            if answers:
                result["answers"] = answers

        return result

    async def _build_user_profile(self, request: ApplyRequest) -> dict:
        """Build user profile dictionary for LLM using resume details from HH.ru."""
        # Fetch resume details from HH.ru
        resume_details = await self.hh_client.get_resume_details(request.resume_id)

        # Extract relevant information from the resume
        experience = resume_details.get("experience", [])
        skills = resume_details.get("skill_set", [])
        education = resume_details.get("education", {}).get("items", [])

        # Format experience
        formatted_experience = ""
        for exp in experience:
            company = exp.get("company", "")
            position = exp.get("position", "")
            start_date = exp.get("start", "")
            end_date = exp.get("end", "") or "Present"
            description = exp.get("description", "")
            formatted_experience += f"{company}, {position}, {start_date} - {end_date}: {description}\n"

        # Format skills
        formatted_skills = ", ".join([skill.get("name", "") for skill in skills]) if skills else request.skills

        # Use resume information or fall back to request data if not available
        return {
            "experience": formatted_experience or request.experience,
            "skills": formatted_skills or request.skills,
            "resume": resume_details.get("description", "") or request.resume,
            "education": education,
            "position": resume_details.get("title", "") or request.position,
            # Add more fields as needed
        }

    async def _can_apply_to_vacancy(self, vacancy: dict) -> tuple[bool, str]:
        """Business rules for determining if we can apply to a vacancy."""
        if vacancy.get("archived", False):
            return False, "Vacancy is archived"

        if not vacancy.get("response_url"):
            return False, "Applications not accepted"

        # Add more business rules here
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
