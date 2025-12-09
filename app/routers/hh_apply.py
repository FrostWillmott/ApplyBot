import logging

import httpx
from fastapi import APIRouter, Cookie, Depends, Request
from starlette.responses import JSONResponse

from app.core.storage import TokenStorage
from app.services.hh_client import HHAPIError, HHClient, get_hh_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hh", tags=["hh"])


@router.get("/resumes")
async def get_user_resumes(
    hh_access_token: str | None = Cookie(None),
    hh: HHClient = Depends(get_hh_client),
):
    """Get user's resumes from HH.ru."""
    if not hh_access_token:
        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            return JSONResponse(
                status_code=401, content={"detail": "Authentication required"}
            )
        access_token = token.access_token
    else:
        access_token = hh_access_token

    try:
        hh._access_token = access_token
        resumes = await hh.get_my_resumes()
        return [
            {
                "id": r.get("id"),
                "title": r.get("title", "Untitled"),
                "status": r.get("status", {}).get("name", "Unknown"),
                "updated_at": r.get("updated_at"),
                "total_views": r.get("total_views", 0),
            }
            for r in resumes
        ]
    except HHAPIError as e:
        logger.error(f"HH API error getting resumes: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": f"HH API error: {e.message}"},
        )
    except httpx.RequestError as e:
        logger.error(f"Network error getting resumes: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Network error connecting to HH.ru"},
        )


@router.get("/vacancies")
async def vacancies(
    text: str,
    page: int = 0,
    per_page: int = 20,
    hh: HHClient = Depends(get_hh_client),
):
    """Search vacancies by text query."""
    data = await hh.list_vacancies(text=text, page=page, per_page=per_page)
    return data


@router.get("/profile")
async def get_user_profile(
    request: Request,
    resume_id: str | None = None,
    hh_access_token: str | None = Cookie(None),
    hh: HHClient = Depends(get_hh_client),
):
    """Get user profile from HH.ru for bulk application."""
    if not hh_access_token:
        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required",
                    "redirect": "/auth/login",
                },
            )
        access_token = token.access_token
    else:
        access_token = hh_access_token

    try:
        profile = await hh.get_user_profile_for_application(
            access_token=access_token, resume_id=resume_id
        )
        return profile
    except ValueError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})
    except HHAPIError as e:
        logger.error(f"HH API error getting profile: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": f"HH API error: {e.message}"},
        )
    except httpx.RequestError as e:
        logger.error(f"Network error getting profile: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Network error connecting to HH.ru"},
        )
