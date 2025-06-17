from typing import Any

import httpx

from app.core.config import settings
from app.core.storage import TokenStorage


class HHClient:
    token_url = "https://hh.ru/oauth/token"
    api_base = "https://api.hh.ru"

    def __init__(self):
        self.client = httpx.AsyncClient(base_url=self.api_base)
        self._token = None

    async def _ensure_token(self):
        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            raise RuntimeError("Token missing or expired")
        self._token = token.access_token
        self.client.headers.update({"Authorization": f"Bearer {self._token}"})

    async def list_vacancies(self, **params) -> dict:
        await self._ensure_token()
        r = await self.client.get("/vacancies", params=params)
        r.raise_for_status()
        return r.json()

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        """Получить полные детали вакансии (description, key_skills и пр.)."""
        await self._ensure_token()
        resp = await self.client.get(f"{self.api_base}/vacancies/{vacancy_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_vacancy_questions(self, vacancy_id: str) -> list[str]:
        """Получить screening questions, если они есть.
        Ответ — { items: [ { id, text }, … ] }
        """
        await self._ensure_token()
        resp = await self.client.get(
            f"{self.api_base}/vacancies/{vacancy_id}/questions"
        )
        if resp.status_code == 404:
            return []  # у многих вакансий нет вопросов
        resp.raise_for_status()
        data = resp.json()
        return [item["text"] for item in data.get("items", [])]

    async def apply(self, vacancy_id: str, resume_id: str, cover_letter: str):
        """Откликнуться на вакансию.
        Документация HH говорит о POST /resumes/{resume_id}/apply?vacancyId=…
        """
        await self._ensure_token()
        resp = await self.client.post(
            f"{self.api_base}/resumes/{resume_id}/apply",
            params={"vacancyId": vacancy_id},
            json={"cover_letter": cover_letter},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_access_token(self, code: str) -> dict:
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
            "code": code,
            "redirect_uri": settings.hh_redirect_uri,
        }
        r = await httpx.AsyncClient().post(self.token_url, data=data)
        r.raise_for_status()
        return r.json()


async def get_hh_client() -> HHClient:
    return HHClient()
