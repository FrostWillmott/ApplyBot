"""API routes for job applications."""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.schemas.apply import ApplyRequest, ApplyResponse, BulkApplyRequest
from app.services.application_service import (
    ApplicationService,
    create_application_service,
)
from app.services.hh_client import HHAPIError, HHClient, get_hh_client
from app.services.llm.dependencies import llm_provider_dep
from app.utils.validators import validate_bulk_application_limits

router = APIRouter(prefix="/apply", tags=["apply"])


async def get_application_service(
    hh_client: HHClient = Depends(get_hh_client),
    llm_provider=Depends(llm_provider_dep),
) -> ApplicationService:
    """Create application service with dependencies."""
    return create_application_service(hh_client, llm_provider)


@router.post("/single/{vacancy_id}", response_model=ApplyResponse)
async def apply_to_vacancy(
    vacancy_id: str,
    request: ApplyRequest,
    service: ApplicationService = Depends(get_application_service),
):
    """Apply to a specific vacancy by ID."""
    try:
        result = await service.apply_to_single_vacancy(vacancy_id, request)

        if result.status == "error":
            raise HTTPException(status_code=400, detail=result.error_detail)

        return result

    except HTTPException:
        raise
    except HHAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk", response_model=list[ApplyResponse])
async def bulk_apply(
    request: BulkApplyRequest,
    service: ApplicationService = Depends(get_application_service),
    max_applications: int = Query(
        default=20, le=50, description="Maximum applications"
    ),
    pages: int = Query(default=1, le=5, description="Search pages to process"),
):
    """Apply to multiple vacancies matching search criteria."""
    try:
        validation = validate_bulk_application_limits(max_applications)
        if not validation.is_valid:
            raise HTTPException(status_code=400, detail=validation.error)

        results = await service.bulk_apply(
            request=request, max_applications=max_applications
        )

        return results

    except HTTPException:
        raise
    except HHAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk/stream")
async def bulk_apply_stream(
    request: BulkApplyRequest,
    service: ApplicationService = Depends(get_application_service),
    max_applications: int = Query(
        default=20, le=50, description="Maximum applications"
    ),
):
    """Stream bulk application progress via Server-Sent Events."""
    validation = validate_bulk_application_limits(max_applications)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.error)

    async def event_generator():
        async for progress in service.bulk_apply_stream(
            request=request, max_applications=max_applications
        ):
            yield {
                "event": progress.event,
                "data": json.dumps(progress.model_dump(), ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.get("/search")
async def search_vacancies(
    text: str,
    page: int = Query(default=0, ge=0),
    per_page: int = Query(default=20, le=100),
    hh_client: HHClient = Depends(get_hh_client),
):
    """Search for vacancies without applying."""
    try:
        results = await hh_client.search_vacancies(
            text=text, page=page, per_page=per_page
        )
        return results
    except HHAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
