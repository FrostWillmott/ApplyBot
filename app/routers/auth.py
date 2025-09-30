# app/routers/auth.py

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.requests import Request

from app.core.config import settings
from app.core.storage import TokenStorage
from app.services.hh_client import HHClient

router = APIRouter(prefix="/auth", tags=["auth"])

# Генерируем state и сохраняем его, чтобы потом проверить подлинность
_state_store: dict[str, str] = {}


@router.get("/login")
async def login(request: Request):
    """Шагаем в OAuth-флоу hh.ru: перенаправляем пользователя
    на страницу авторизации HH с client_id и redirect_uri.
    """
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
async def callback(code: str, state: str):
    """Обрабатываем редирект от hh.ru.
    Проверяем state, обмениваем code на токен и сохраняем его.
    """
    # Проверяем, что state тот же самый
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    hh = HHClient()
    token_data = await hh.get_access_token(code)

    # Сохраняем токены в БД для использования другими сервисами
    saved_token = await TokenStorage.save(
        {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data["expires_in"],
            "obtained_at": token_data.get("obtained_at"),
        }
    )

    # Убираем state из временного хранилища
    _state_store.pop(state, None)

    # Перенаправляем пользователя на главную страницу после успешной аутентификации
    return RedirectResponse(url="/")
