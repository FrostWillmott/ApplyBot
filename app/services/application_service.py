"""Application service for job applications."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.redis_client import ProcessedVacancyCache
from app.core.storage import async_session
from app.models.application import ApplicationHistory
from app.schemas.apply import (
    ApplyRequest,
    ApplyResponse,
    BulkApplyProgress,
    BulkApplyRequest,
)
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
        use_cover_letter: bool = True,
    ) -> ApplyResponse:
        """Apply to a single vacancy."""
        validation_result = await validate_application_request(request)
        if not validation_result.is_valid:
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                error_detail=f"Invalid request: {validation_result.error}",
            )

        vacancy = None  # Initialize to avoid UnboundLocalError
        try:
            if await self._has_already_applied(vacancy_id, request.resume_id):
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    error_detail="Already applied to this vacancy",
                )

            vacancy = await self.hh_client.get_vacancy_details(vacancy_id)
            can_apply, reason = await self._can_apply_to_vacancy(
                vacancy, use_cover_letter=use_cover_letter
            )
            if not can_apply:
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    vacancy_title=vacancy.get("name"),
                    error_detail=reason,
                )

            application_content = await self._generate_application_content(
                vacancy, request, use_cover_letter=use_cover_letter
            )

            hh_response = await self.hh_client.apply(
                vacancy_id=vacancy_id,
                resume_id=request.resume_id,
                cover_letter=application_content.get("cover_letter"),
                answers=application_content.get("answers"),
            )

            await self._record_application(
                vacancy_id=vacancy_id,
                request=request,
                response=hh_response,
                user_id=user_id,
            )

            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="success",
                vacancy_title=vacancy.get("name"),
                cover_letter=application_content.get("cover_letter"),
                hh_response=hh_response,
            )

        except HTTPException as e:
            logger.error(
                f"Application failed for vacancy {vacancy_id}: HTTP {e.status_code} - {e.detail}"
            )

            # specialized handling for known skip conditions
            if e.status_code == 403 and "test" in str(e.detail).lower():
                return ApplyResponse(
                    vacancy_id=vacancy_id,
                    status="skipped",
                    vacancy_title=vacancy.get("name") if vacancy else None,
                    error_detail="Vacancy requires mandatory test",
                )

            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                vacancy_title=vacancy.get("name") if vacancy else None,
                error_detail=f"HTTP {e.status_code}: {e.detail}",
            )
        except httpx.RequestError as e:
            logger.error(f"Network error for vacancy {vacancy_id}: {e}")
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                vacancy_title=vacancy.get("name") if vacancy else None,
                error_detail=f"Network error: {e}",
            )
        except ValueError as e:
            logger.error(f"Validation error for vacancy {vacancy_id}: {e}")
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                vacancy_title=vacancy.get("name") if vacancy else None,
                error_detail=str(e),
            )
        except SQLAlchemyError as e:
            logger.error(f"Database error for vacancy {vacancy_id}: {e}")
            return ApplyResponse(
                vacancy_id=vacancy_id,
                status="error",
                vacancy_title=vacancy.get("name") if vacancy else None,
                error_detail="Database error",
            )

    async def bulk_apply(
        self,
        request: BulkApplyRequest,
        max_applications: int = 20,
        user_id: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[ApplyResponse]:
        """Apply to multiple vacancies based on search criteria."""
        logger.info(f"Starting bulk application for: {request.position}")

        filter_engine = ApplicationFilter(request)
        results = []
        applied_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 3  # Circuit breaker threshold
        max_consecutive_errors = 3  # Circuit breaker threshold
        adaptive_delay = 3.0  # Start with 3 seconds delay
        min_delay = 2.0
        max_delay = 30.0

        try:
            logger.info("Fetching previously applied vacancies from HH.ru...")
            already_applied_ids = await self.hh_client.get_applied_vacancy_ids()
            logger.info(
                f"User has {len(already_applied_ids)} existing applications on HH.ru"
            )

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

                # Circuit breaker: stop if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        f"Circuit breaker triggered: {consecutive_errors} consecutive errors. "
                        f"Stopping bulk application to avoid further DDoS protection blocks."
                    )
                    break

                vacancy_id = str(vacancy.get("id", ""))

                if vacancy_id in already_applied_ids:
                    skipped_already_applied += 1
                    results.append(
                        ApplyResponse(
                            vacancy_id=vacancy_id,
                            status="skipped",
                            vacancy_title=vacancy.get("name"),
                            error_detail="Already applied (HH.ru)",
                        )
                    )
                    continue

                should_apply, filter_reason = filter_engine.should_apply(vacancy)
                if not should_apply:
                    results.append(
                        ApplyResponse(
                            vacancy_id=vacancy_id,
                            status="skipped",
                            vacancy_title=vacancy.get("name"),
                            error_detail=f"Filtered: {filter_reason}",
                        )
                    )
                    # Cache filtered vacancy to avoid re-checking
                    await self._cache_processed_vacancy(vacancy_id)
                    continue

                use_cover_letter = getattr(request, "use_cover_letter", True)
                response = await self.apply_to_single_vacancy(
                    vacancy_id,
                    request,
                    user_id,
                    use_cover_letter=use_cover_letter,
                )
                results.append(response)
                # Cache processed vacancy (applied or error)
                await self._cache_processed_vacancy(vacancy_id)

                if response.status == "success":
                    applied_count += 1
                    consecutive_errors = 0  # Reset error counter on success
                    # Adaptive delay: reduce delay after success, but keep minimum
                    adaptive_delay = max(min_delay, adaptive_delay * 0.8)
                    # Add random jitter (0-2 seconds) to mimic human behavior
                    delay = adaptive_delay + random.uniform(0, 2)
                    logger.info(
                        f"Application successful. Waiting {delay:.1f}s before next application "
                        f"(adaptive delay: {adaptive_delay:.1f}s)"
                    )
                    await asyncio.sleep(delay)
                elif response.status == "error":
                    consecutive_errors += 1
                    # Adaptive delay: increase delay exponentially on errors
                    adaptive_delay = min(max_delay, adaptive_delay * 1.5)

                    if "429" in str(response.error_detail) or "403" in str(
                        response.error_detail
                    ):
                        # DDoS protection or rate limit - wait much longer
                        delay = adaptive_delay + random.uniform(10, 30)
                        logger.warning(
                            f"Rate limit/DDoS protection detected. "
                            f"Consecutive errors: {consecutive_errors}/{max_consecutive_errors}. "
                            f"Waiting {delay:.1f}s (adaptive delay: {adaptive_delay:.1f}s)"
                        )
                        await asyncio.sleep(delay)
                    else:
                        # Other error - shorter delay
                        delay = adaptive_delay * 0.5 + random.uniform(5, 15)
                        logger.warning(
                            f"Application error. Consecutive errors: {consecutive_errors}/{max_consecutive_errors}. "
                            f"Waiting {delay:.1f}s before retry"
                        )
                        await asyncio.sleep(delay)

            logger.info(
                f"Bulk application completed: {applied_count} sent, "
                f"{skipped_already_applied} skipped (already applied)"
            )
            return results

        except httpx.RequestError as e:
            logger.error(f"Bulk application network error: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Bulk application database error: {e}")
            raise
        except ValueError as e:
            logger.error(f"Bulk application validation error: {e}")
            raise

    async def bulk_apply_stream(
        self,
        request: BulkApplyRequest,
        max_applications: int = 20,
        user_id: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> AsyncIterator[BulkApplyProgress]:
        """Stream bulk application progress via Server-Sent Events."""
        logger.info(f"Starting streaming bulk application for: {request.position}")

        filter_engine = ApplicationFilter(request)
        success_count = 0
        skipped_count = 0
        error_count = 0
        current = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        adaptive_delay = 3.0
        min_delay = 2.0
        max_delay = 30.0

        try:
            # Emit start event
            yield BulkApplyProgress(
                event="start",
                current=0,
                total=max_applications,
                message="Fetching previously applied vacancies...",
            )

            already_applied_ids = await self.hh_client.get_applied_vacancy_ids()
            logger.info(
                f"User has {len(already_applied_ids)} existing applications on HH.ru"
            )

            yield BulkApplyProgress(
                event="progress",
                current=0,
                total=max_applications,
                message=f"Searching vacancies for: {request.position}...",
            )

            vacancies = await self._search_vacancies_for_bulk(request, max_applications)

            if not vacancies:
                logger.warning(f"No vacancies found for: {request.position}")
                yield BulkApplyProgress(
                    event="complete",
                    current=0,
                    total=0,
                    success_count=0,
                    skipped_count=0,
                    error_count=0,
                    message="No vacancies found matching your criteria",
                )
                return

            total = min(len(vacancies), max_applications)

            yield BulkApplyProgress(
                event="progress",
                current=0,
                total=total,
                message=f"Found {len(vacancies)} vacancies, processing up to {total}...",
            )

            for vacancy in vacancies:
                if cancel_check and cancel_check():
                    logger.info("Bulk application cancelled by user")
                    yield BulkApplyProgress(
                        event="cancelled",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        message="Application cancelled by user",
                    )
                    return

                if success_count >= max_applications:
                    break

                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        f"Circuit breaker triggered: {consecutive_errors} consecutive errors"
                    )
                    yield BulkApplyProgress(
                        event="error",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        message="Too many consecutive errors, stopping",
                    )
                    return

                vacancy_id = str(vacancy.get("id", ""))
                vacancy_title = vacancy.get("name", "Unknown")
                current += 1

                # Check if already applied
                if vacancy_id in already_applied_ids:
                    skipped_count += 1
                    result = ApplyResponse(
                        vacancy_id=vacancy_id,
                        status="skipped",
                        vacancy_title=vacancy_title,
                        error_detail="Already applied (HH.ru)",
                    )
                    yield BulkApplyProgress(
                        event="progress",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        result=result,
                        message=f"Skipped: {vacancy_title} (already applied)",
                    )
                    continue

                # Apply filter
                should_apply, filter_reason = filter_engine.should_apply(vacancy)
                if not should_apply:
                    skipped_count += 1
                    result = ApplyResponse(
                        vacancy_id=vacancy_id,
                        status="skipped",
                        vacancy_title=vacancy_title,
                        error_detail=f"Filtered: {filter_reason}",
                    )
                    yield BulkApplyProgress(
                        event="progress",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        result=result,
                        message=f"Skipped: {vacancy_title} ({filter_reason})",
                    )
                    # Cache filtered vacancy to avoid re-checking
                    await self._cache_processed_vacancy(vacancy_id)
                    continue

                # Apply to vacancy
                use_cover_letter = getattr(request, "use_cover_letter", True)
                response = await self.apply_to_single_vacancy(
                    vacancy_id,
                    request,
                    user_id,
                    use_cover_letter=use_cover_letter,
                )
                # Cache processed vacancy (applied or error)
                await self._cache_processed_vacancy(vacancy_id)

                if response.status == "success":
                    success_count += 1
                    consecutive_errors = 0
                    adaptive_delay = max(min_delay, adaptive_delay * 0.8)
                    delay = adaptive_delay + random.uniform(0, 2)

                    yield BulkApplyProgress(
                        event="progress",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        result=response,
                        message=f"Applied: {vacancy_title}",
                    )

                    await asyncio.sleep(delay)

                elif response.status == "error":
                    error_count += 1
                    consecutive_errors += 1
                    adaptive_delay = min(max_delay, adaptive_delay * 1.5)

                    yield BulkApplyProgress(
                        event="progress",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        result=response,
                        message=f"Error: {vacancy_title} - {response.error_detail}",
                    )

                    if "429" in str(response.error_detail) or "403" in str(
                        response.error_detail
                    ):
                        delay = adaptive_delay + random.uniform(10, 30)
                    else:
                        delay = adaptive_delay * 0.5 + random.uniform(5, 15)
                    await asyncio.sleep(delay)

                else:
                    skipped_count += 1
                    yield BulkApplyProgress(
                        event="progress",
                        current=current,
                        total=total,
                        success_count=success_count,
                        skipped_count=skipped_count,
                        error_count=error_count,
                        result=response,
                        message=f"Skipped: {vacancy_title}",
                    )

            # Complete event
            yield BulkApplyProgress(
                event="complete",
                current=current,
                total=total,
                success_count=success_count,
                skipped_count=skipped_count,
                error_count=error_count,
                message=f"Completed! {success_count} applications sent",
            )

        except httpx.RequestError as e:
            logger.error(f"Streaming bulk application network error: {e}")
            yield BulkApplyProgress(
                event="error",
                current=current,
                total=max_applications,
                success_count=success_count,
                skipped_count=skipped_count,
                error_count=error_count,
                message=f"Network error: {e!s}",
            )
        except SQLAlchemyError as e:
            logger.error(f"Streaming bulk application database error: {e}")
            yield BulkApplyProgress(
                event="error",
                current=current,
                total=max_applications,
                success_count=success_count,
                skipped_count=skipped_count,
                error_count=error_count,
                message=f"Database error: {e!s}",
            )
        except ValueError as e:
            logger.error(f"Streaming bulk application validation error: {e}")
            yield BulkApplyProgress(
                event="error",
                current=current,
                total=max_applications,
                success_count=success_count,
                skipped_count=skipped_count,
                error_count=error_count,
                message=f"Validation error: {e!s}",
            )

    async def _search_vacancies_for_bulk(
        self, request: BulkApplyRequest, max_applications: int
    ) -> list[dict]:
        """Search and collect vacancies with multiple search queries.

        Parses position string to create multiple search queries:
        - "Python-разработчик (Django, FastAPI)" becomes:
          - "Python разработчик"
          - "Django"
          - "FastAPI"

        Uses Redis cache to skip already-processed vacancy IDs.
        """
        employment = None
        if request.employment_types and len(request.employment_types) == 1:
            employment = request.employment_types[0]

        schedule = None
        if request.remote_only:
            schedule = "remote"
        elif request.preferred_schedule and len(request.preferred_schedule) == 1:
            schedule = request.preferred_schedule[0]

        # Parse position into multiple search queries
        search_queries = self._parse_position_to_queries(request.position)
        logger.info(
            f"Parsed position '{request.position}' into {len(search_queries)} queries: "
            f"{search_queries}"
        )

        all_vacancies: dict[str, dict] = {}  # Use dict to deduplicate by ID
        skipped_cached = 0

        for query in search_queries:
            if len(all_vacancies) >= max_applications * 3:
                break  # Enough vacancies collected

            logger.info(
                f"Searching: text='{query}', experience={request.experience_level}, "
                f"schedule={schedule}, salary={request.salary_min}"
            )

            page = 0
            max_pages = 3

            while len(all_vacancies) < max_applications * 3 and page < max_pages:
                search_results = await self.hh_client.search_vacancies(
                    text=query,
                    experience=request.experience_level,
                    schedule=schedule,
                    employment=employment,
                    salary=request.salary_min,
                    only_with_salary=bool(request.salary_min),
                    page=page,
                    per_page=100,
                )

                page_vacancies = search_results.get("items", [])
                if not page_vacancies:
                    break

                # Filter out already-processed vacancies using Redis cache
                vacancy_ids = [str(v.get("id", "")) for v in page_vacancies]
                new_ids = await ProcessedVacancyCache.filter_new(vacancy_ids)
                new_ids_set = set(new_ids)
                skipped_cached += len(vacancy_ids) - len(new_ids)

                # Add new vacancies (deduplicated by ID)
                for v in page_vacancies:
                    vid = str(v.get("id", ""))
                    if vid in new_ids_set and vid not in all_vacancies:
                        all_vacancies[vid] = v

                page += 1
                total_found = search_results.get("found", 0)
                logger.info(
                    f"  Query '{query}' page {page}: +{len(page_vacancies)} vacancies "
                    f"(total unique: {len(all_vacancies)}, HH total: {total_found})"
                )

        result = list(all_vacancies.values())
        logger.info(
            f"Collected {len(result)} unique vacancies from {len(search_queries)} queries "
            f"(skipped {skipped_cached} already processed)"
        )
        return result

    def _parse_position_to_queries(self, position: str) -> list[str]:
        """Parse position string into multiple search queries.

        Examples:
        - "Python-разработчик (Django, FastAPI)" ->
          ["Python разработчик", "Django разработчик", "FastAPI разработчик"]
        - "Backend developer" -> ["Backend developer"]
        """
        import re

        queries = []

        # Extract content in parentheses
        paren_match = re.search(r"\(([^)]+)\)", position)
        keywords_in_parens = []
        if paren_match:
            # Split by comma and clean up
            keywords_in_parens = [
                kw.strip() for kw in paren_match.group(1).split(",") if kw.strip()
            ]

        # Get main part (before parentheses), clean it up
        main_part = re.sub(r"\s*\([^)]*\)\s*", "", position).strip()
        # Replace dashes/hyphens with spaces (including en-dash and em-dash)
        main_part_clean = re.sub(r"[-\u2013\u2014]", " ", main_part)
        # Normalize multiple spaces
        main_part_clean = re.sub(r"\s+", " ", main_part_clean).strip()

        # Add main query
        if main_part_clean:
            queries.append(main_part_clean)

        # Add queries for each keyword in parentheses
        # Combined with base role word (разработчик, developer, etc.)
        role_words = ["разработчик", "developer", "инженер", "engineer", "программист"]
        base_role = None
        for word in role_words:
            if word in main_part_clean.lower():
                # Extract the role word with proper case
                match = re.search(rf"\b({word})\b", main_part_clean, re.IGNORECASE)
                if match:
                    base_role = match.group(1)
                    break

        for keyword in keywords_in_parens:
            if base_role:
                # "Django" + "разработчик" -> "Django разработчик"
                queries.append(f"{keyword} {base_role}")
            else:
                queries.append(keyword)

        return queries if queries else [position]

    async def _cache_processed_vacancy(self, vacancy_id: str) -> None:
        """Cache a vacancy ID after it has been processed (applied or skipped)."""
        await ProcessedVacancyCache.add_many([vacancy_id])

    async def _generate_application_content(
        self,
        vacancy: dict,
        request: ApplyRequest,
        use_cover_letter: bool = True,
    ) -> dict:
        """Generate cover letter and answer screening questions.

        Note: Questions are always answered when available, regardless of
        use_cover_letter setting. The LLM is used for both cover letters
        and screening question answers.
        """
        result = {"cover_letter": None, "answers": None}
        user_profile = await self._build_user_profile(request)

        # Generate cover letter if enabled
        if use_cover_letter:
            cover_letter = await self.llm_provider.generate_cover_letter(
                vacancy, user_profile
            )
            result["cover_letter"] = cover_letter
        else:
            logger.info(
                f"Skipping cover letter generation for vacancy {vacancy.get('id')}"
            )

        # Always try to answer screening questions (they can be required)
        questions = await self.hh_client.get_vacancy_questions(vacancy["id"])
        if questions:
            # Filter out questions with external links
            answerable_questions = self._filter_answerable_questions(questions)

            if answerable_questions:
                logger.info(
                    f"Vacancy {vacancy.get('id')} has {len(answerable_questions)} "
                    f"answerable screening questions (total: {len(questions)})"
                )
                answers = await self.llm_provider.answer_screening_questions(
                    answerable_questions, vacancy, user_profile
                )
                if answers:
                    logger.info(
                        f"Generated {len(answers)} answers for screening questions"
                    )
                    result["answers"] = answers
            elif len(questions) > 0:
                logger.info(
                    f"Vacancy {vacancy.get('id')}: all {len(questions)} questions "
                    "have external links, skipping"
                )

        return result

    def _filter_answerable_questions(self, questions: list[dict]) -> list[dict]:
        """Filter out questions that require external resources.

        Questions with URLs pointing to external resources (not text-based)
        cannot be answered by the LLM.
        """
        answerable = []

        for q in questions:
            question_text = q.get("text", q.get("question", ""))

            # Skip questions that are just links
            if self._is_external_link_question(question_text):
                logger.debug(f"Skipping external link question: {question_text[:100]}")
                continue

            # Skip questions with required_url field (external test)
            if q.get("required_url") or q.get("url"):
                logger.debug(f"Skipping question with required URL: {q}")
                continue

            answerable.append(q)

        return answerable

    def _is_external_link_question(self, text: str) -> bool:
        """Check if question text is primarily an external link."""
        if not text:
            return False

        text_lower = text.lower().strip()

        # Common patterns for external test links
        external_patterns = [
            "http://",
            "https://",
            "пройдите тест по ссылке",
            "перейдите по ссылке",
            "выполните задание по ссылке",
            "complete the test at",
            "follow the link",
            "go to the link",
        ]

        for pattern in external_patterns:
            if pattern in text_lower:
                # Check if URL is not hh.ru (hh.ru links are internal)
                if "http" in pattern:
                    if "hh.ru" not in text_lower:
                        return True
                else:
                    return True

        return False

    async def _build_user_profile(self, request: ApplyRequest) -> dict:
        """Build user profile dictionary for LLM."""
        resume_details = await self.hh_client.get_resume_details(request.resume_id)

        experience = resume_details.get("experience", [])
        skills = resume_details.get("skill_set", [])
        education = resume_details.get("education", {}).get("items", [])

        # Extract name
        first_name = resume_details.get("first_name", "")
        last_name = resume_details.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()

        # Extract email from contacts
        email = ""
        contacts = resume_details.get("contact", [])
        for contact in contacts:
            if contact.get("type", {}).get("id") == "email":
                email = contact.get("value", "")
                break

        formatted_experience = ""
        for exp in experience:
            company = exp.get("company", "")
            position = exp.get("position", "")
            start_date = exp.get("start", "")
            end_date = exp.get("end", "") or "Present"
            description = exp.get("description", "")
            formatted_experience += (
                f"{company}, {position}, {start_date} - {end_date}: {description}\n"
            )

        if skills:
            if skills and isinstance(skills[0], dict):
                formatted_skills = ", ".join(
                    [skill.get("name", "") for skill in skills]
                )
            else:
                formatted_skills = ", ".join([str(skill) for skill in skills])
        else:
            formatted_skills = request.skills

        return {
            "name": full_name,
            "email": email,
            "experience": formatted_experience or request.experience,
            "skills": formatted_skills or request.skills,
            "resume": resume_details.get("description", "") or request.resume,
            "education": education,
            "position": resume_details.get("title", "") or request.position,
        }

    async def _can_apply_to_vacancy(
        self, vacancy: dict, use_cover_letter: bool = True
    ) -> tuple[bool, str]:
        """Check if we can apply to a vacancy."""
        vacancy_id = vacancy.get("id", "unknown")
        vacancy_name = vacancy.get("name", "unknown")

        if vacancy.get("archived", False):
            logger.info(f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - archived")
            return False, "Vacancy is archived"

        relations = vacancy.get("relations", [])
        if "got_response" in relations or "response" in relations:
            logger.info(
                f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - already applied"
            )
            return False, "Already applied to this vacancy"

        # Check if vacancy requires cover letter but user disabled it
        if vacancy.get("response_letter_required", False) and not use_cover_letter:
            logger.info(
                f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - requires cover letter"
            )
            return False, "Vacancy requires cover letter (enable AI assistant)"

        # Check for external tests (tests with links to external resources)
        if self._has_external_test(vacancy):
            logger.info(
                f"Vacancy {vacancy_id} ({vacancy_name}): SKIPPED - external test required"
            )
            return False, "Vacancy requires external test (cannot be answered via API)"

        logger.info(f"Vacancy {vacancy_id} ({vacancy_name}): CAN APPLY")
        return True, ""

    def _has_external_test(self, vacancy: dict) -> bool:
        """Check if vacancy has an external test that cannot be answered via API.

        External tests are those that require going to an external URL
        (not HH.ru's built-in questions that we can answer via API).
        """
        # Check for test field with external link
        test = vacancy.get("test")
        if test:
            # If test has a URL pointing outside HH.ru, it's external
            test_url = test.get("url", "") or test.get("href", "")
            if test_url and not test_url.startswith("https://hh.ru"):
                logger.debug(f"Vacancy has external test URL: {test_url}")
                return True

            # Check if test is required and has external indicator
            if test.get("required", False):
                # If there's no way to answer via API, it's external
                # HH.ru API questions are fetched via /vacancies/{id}/questions
                # External tests won't have API-answerable questions
                return True

        # Check for branded_template with external links
        branded = vacancy.get("branded_template")
        if branded:
            # Some branded vacancies have external application forms
            if branded.get("external_form_url"):
                return True

        return False

    async def _has_already_applied(self, vacancy_id: str, resume_id: str) -> bool:
        """Check if we've already applied to this vacancy."""
        async with async_session() as session:
            query = select(ApplicationHistory).where(
                ApplicationHistory.vacancy_id == vacancy_id,
                ApplicationHistory.resume_id == resume_id,
            )

            result = await session.execute(query)
            application = result.scalar_one_or_none()

            return application is not None

    async def _record_application(
        self,
        vacancy_id: str,
        request: ApplyRequest,
        response: dict,
        user_id: str | None = None,
    ):
        """Record application in database for tracking."""
        async with async_session() as session:
            application = ApplicationHistory(
                vacancy_id=vacancy_id,
                resume_id=request.resume_id,
                user_id=user_id,
                applied_at=datetime.now(UTC).replace(tzinfo=None),
                hh_response=response,
            )
            session.add(application)
            await session.commit()


# Factory function for dependency injection
def create_application_service(
    hh_client: HHClient, llm_provider: LLMProvider
) -> ApplicationService:
    """Factory function to create ApplicationService with dependencies."""
    return ApplicationService(hh_client, llm_provider)
