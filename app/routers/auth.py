"""Authentication router for HH.ru OAuth flow."""

import secrets

from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.requests import Request

from app.core.config import settings
from app.core.storage import TokenStorage
from app.services.hh_client import HHClient

router = APIRouter(prefix="/auth", tags=["auth"])

_state_store: dict[str, str] = {}


@router.get("/login")
async def login(request: Request):
    """Initiate OAuth flow with HH.ru."""
    state = secrets.token_urlsafe(16)
    _state_store[state] = request.client.host
    params = {
        "response_type": "code",
        "client_id": settings.hh_client_id,
        "state": state,
        "redirect_uri": settings.hh_redirect_uri,
    }
    url = "https://hh.ru/oauth/authorize?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    return RedirectResponse(url)


@router.get("/callback")
async def callback(code: str, state: str, response: Response):
    """Handle OAuth callback from HH.ru."""
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    hh = HHClient()
    token_data = await hh.get_access_token(code)

    saved_token = await TokenStorage.save(
        {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data["expires_in"],
            "obtained_at": token_data.get("obtained_at"),
        }
    )

    _state_store.pop(state, None)

    redirect_response = RedirectResponse(url="/")
    redirect_response.set_cookie(
        key="hh_access_token",
        value=saved_token.access_token,
        max_age=token_data["expires_in"],
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    redirect_response.set_cookie(
        key="hh_token_id",
        value=str(saved_token.id),
        max_age=token_data["expires_in"],
        httponly=True,
        samesite="lax",
    )

    return redirect_response


@router.get("/status")
async def auth_status(
    request: Request,
    hh_access_token: str | None = Cookie(None),
):
    """Check user authentication status."""
    if hh_access_token:
        try:
            hh = HHClient()
            user_info = await hh.get_user_info(hh_access_token)
            return JSONResponse(
                status_code=200,
                content={
                    "authenticated": True,
                    "user_id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "first_name": user_info.get("first_name"),
                    "last_name": user_info.get("last_name"),
                },
            )
        except Exception:
            return JSONResponse(
                status_code=200,
                content={"authenticated": False, "reason": "Invalid token"},
            )

    token = await TokenStorage.get_latest()
    if token and not token.is_expired():
        return JSONResponse(
            status_code=200,
            content={"authenticated": True, "source": "database"},
        )

    return JSONResponse(
        status_code=200,
        content={"authenticated": False, "reason": "No token found"},
    )
