from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.apply import ApplyRequest, ApplyResponse, BulkApplyRequest
from app.services.hh_client import HHClient, get_hh_client
from app.services.llm.dependencies import llm_provider_dep
from app.services.prompt_builder import build_application_prompt

router = APIRouter(prefix="/apply", tags=["apply"])


@router.post("/single/{vacancy_id}", response_model=ApplyResponse)
async def apply_to_vacancy(
        vacancy_id: str,
        req: ApplyRequest,
        hh: HHClient = Depends(get_hh_client),
        llm=Depends(llm_provider_dep),
):
    """Apply to a specific vacancy by ID.

    - Fetches full vacancy details
    - Generates personalized cover letter using LLM
    - Submits application to hh.ru
    """
    try:
        # Get full vacancy details
        resp = await hh.client.get(f"/vacancies/{vacancy_id}")
        resp.raise_for_status()
        vacancy = resp.json()

        # Build prompt and generate application
        prompt = build_application_prompt(req, vacancy)
        application_package = await llm.generate(prompt)

        # Submit application
        result = await hh.apply(
            vacancy_id=vacancy_id,
            resume_id=req.resume_id,  # Added to schema
            cover_letter=application_package
        )

        return ApplyResponse(
            vacancy_id=vacancy_id,
            status="success",
            hh_response=result,
            cover_letter=application_package
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Application failed: {e!s}"
        )


@router.post("/bulk", response_model=list[ApplyResponse])
async def bulk_apply(
        req: BulkApplyRequest,
        hh: HHClient = Depends(get_hh_client),
        llm=Depends(llm_provider_dep),
        max_applications: int = Query(default=20, le=50, description="Maximum applications to send"),
        pages: int = Query(default=1, le=5, description="Number of search result pages to process")
):
    """Apply to multiple vacancies matching search criteria.

    - Searches for vacancies based on position/keywords
    - Applies to each matching vacancy up to the specified limit
    - Returns results for all application attempts
    """
    try:
        # Search for vacancies
        search_results = await hh.list_vacancies(
            text=req.position,
            page=0,
            per_page=min(max_applications, pages * 20)
        )

        vacancies = search_results.get("items", [])

        if not vacancies:
            raise HTTPException(
                status_code=404,
                detail=f"No vacancies found for position: {req.position}"
            )

        results = []
        applied_count = 0

        for vacancy in vacancies:
            if applied_count >= max_applications:
                break

            try:
                # Build application for this vacancy
                prompt = build_application_prompt(req, vacancy)
                cover_letter = await llm.generate(prompt)

                # Submit application
                hh_result = await hh.apply(
                    vacancy_id=vacancy["id"],
                    resume_id=req.resume_id,
                    cover_letter=cover_letter
                )

                results.append(ApplyResponse(
                    vacancy_id=vacancy["id"],
                    status="success",
                    hh_response=hh_result,
                    cover_letter=cover_letter,
                    vacancy_title=vacancy.get("name", "Unknown")
                ))
                applied_count += 1

            except Exception as e:
                results.append(ApplyResponse(
                    vacancy_id=vacancy["id"],
                    status="error",
                    error_detail=str(e),
                    vacancy_title=vacancy.get("name", "Unknown")
                ))

        return results

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Bulk application failed: {e!s}"
        )


@router.get("/search")
async def search_vacancies(
        text: str,
        page: int = Query(default=0, ge=0),
        per_page: int = Query(default=20, le=100),
        hh: HHClient = Depends(get_hh_client),
):
    """Search for vacancies without applying.

    Useful for previewing available positions before bulk application.
    """
    try:
        results = await hh.list_vacancies(
            text=text,
            page=page,
            per_page=per_page
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Search failed: {e!s}"
        )
