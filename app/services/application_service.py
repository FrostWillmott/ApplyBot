from app.schemas.apply import ApplyRequest, ApplyResponse, BulkApplyRequest
from app.services.hh_client import HHClient
from app.services.llm.base import LLMProvider
from app.services.prompt_builder import build_application_prompt


class ApplicationService:
    """Service for handling job applications with business logic."""

    def __init__(self, hh_client: HHClient, llm_provider: LLMProvider):
        self.hh_client = hh_client
        self.llm_provider = llm_provider

    async def apply_to_single_vacancy(
            self,
            vacancy_id: str,
            request: ApplyRequest
    ) -> ApplyResponse:
        """Apply to a single vacancy by ID."""
        # Get full vacancy details
        vacancy = await self.hh_client.get_vacancy_details(vacancy_id)

        # Get screening questions if any
        questions = await self.hh_client.get_vacancy_questions(vacancy_id)
        if questions:
            vacancy["questions"] = questions

        # Generate application content
        prompt = build_application_prompt(request, vacancy)
        application_content = await self.llm_provider.generate(prompt)

        # Submit application
        hh_response = await self.hh_client.apply(
            vacancy_id=vacancy_id,
            resume_id=request.resume_id,
            cover_letter=application_content
        )

        return ApplyResponse(
            vacancy_id=vacancy_id,
            status="success",
            vacancy_title=vacancy.get("name", "Unknown"),
            cover_letter=application_content,
            hh_response=hh_response
        )

    async def bulk_apply(
            self,
            request: BulkApplyRequest,
            max_applications: int = 20
    ) -> list[ApplyResponse]:
        """Apply to multiple vacancies matching criteria."""
        # Search for vacancies
        search_results = await self.hh_client.list_vacancies(
            text=request.position,
            per_page=min(max_applications, 100)
        )

        vacancies = search_results.get("items", [])
        results = []
        applied_count = 0

        for vacancy in vacancies:
            if applied_count >= max_applications:
                break

            # Apply filters
            if not self._should_apply_to_vacancy(vacancy, request):
                results.append(ApplyResponse(
                    vacancy_id=vacancy["id"],
                    status="skipped",
                    vacancy_title=vacancy.get("name", "Unknown"),
                    error_detail="Filtered out by criteria"
                ))
                continue

            try:
                # Generate and submit application
                response = await self._apply_to_vacancy(vacancy, request)
                results.append(response)
                applied_count += 1

            except Exception as e:
                results.append(ApplyResponse(
                    vacancy_id=vacancy["id"],
                    status="error",
                    vacancy_title=vacancy.get("name", "Unknown"),
                    error_detail=str(e)
                ))

        return results

    async def _apply_to_vacancy(
            self,
            vacancy: dict,
            request: ApplyRequest
    ) -> ApplyResponse:
        """Apply to a single vacancy (internal method)."""
        vacancy_id = vacancy["id"]

        # Get additional details if needed
        if "description" not in vacancy:
            vacancy = await self.hh_client.get_vacancy_details(vacancy_id)

        # Generate application
        prompt = build_application_prompt(request, vacancy)
        cover_letter = await self.llm_provider.generate(prompt)

        # Submit application
        hh_response = await self.hh_client.apply(
            vacancy_id=vacancy_id,
            resume_id=request.resume_id,
            cover_letter=cover_letter
        )

        return ApplyResponse(
            vacancy_id=vacancy_id,
            status="success",
            vacancy_title=vacancy.get("name", "Unknown"),
            cover_letter=cover_letter,
            hh_response=hh_response
        )

    def _should_apply_to_vacancy(
            self,
            vacancy: dict,
            request: BulkApplyRequest
    ) -> bool:
        """Check if we should apply to this vacancy based on filters."""
        # Check excluded companies
        if request.exclude_companies:
            employer_name = vacancy.get("employer", {}).get("name", "").lower()
            for excluded in request.exclude_companies:
                if excluded.lower() in employer_name:
                    return False

        # Check salary requirements
        if request.salary_min:
            salary = vacancy.get("salary")
            if salary:
                salary_from = salary.get("from")
                if salary_from and salary_from < request.salary_min:
                    return False
            else:
                # No salary info - might want to skip or include based on preferences
                pass

        # Check remote work requirement
        if request.remote_only:
            schedule = vacancy.get("schedule", {}).get("name", "").lower()
            if "удален" not in schedule and "remote" not in schedule:
                return False

        return True
