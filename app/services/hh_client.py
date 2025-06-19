from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.storage import TokenStorage


class HHClient:
    """HeadHunter API client with improved error handling and logging."""

    token_url = "https://hh.ru/oauth/token"
    api_base = "https://api.hh.ru"

    def __init__(self):
        self.client = httpx.AsyncClient(base_url=self.api_base)
        self._token = None

    async def _ensure_token(self):
        """Ensure we have a valid access token."""
        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            raise HTTPException(
                status_code=401,
                detail="No valid HH.ru token available. Please re-authenticate."
            )
        self._token = token.access_token
        self.client.headers.update({"Authorization": f"Bearer {self._token}"})

    async def list_vacancies(self, **params) -> dict:
        """Search for vacancies with given parameters."""
        await self._ensure_token()
        try:
            response = await self.client.get("/vacancies", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"HH API error: {e.response.text}"
            )

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        """Get full vacancy details including description and requirements."""
        await self._ensure_token()
        try:
            response = await self.client.get(f"/vacancies/{vacancy_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Vacancy {vacancy_id} not found"
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch vacancy: {e.response.text}"
            )

    async def get_vacancy_questions(self, vacancy_id: str) -> list[str]:
        """Get screening questions for a vacancy if they exist."""
        await self._ensure_token()
        try:
            response = await self.client.get(f"/vacancies/{vacancy_id}/questions")
            if response.status_code == 404:
                return []  # No questions for this vacancy
            response.raise_for_status()
            data = response.json()
            return [item["text"] for item in data.get("items", [])]
        except httpx.HTTPStatusError as e:
            # Log warning but don't fail the application
            print(f"Warning: Could not fetch questions for vacancy {vacancy_id}: {e}")
            return []

    async def apply(
            self,
            vacancy_id: str,
            resume_id: str,
            cover_letter: str,
            answers: list[str] | None = None
    ) -> dict:
        """Submit application to a vacancy.

        Args:
            vacancy_id: The ID of the vacancy to apply to
            resume_id: The ID of the resume to use for application
            cover_letter: Generated cover letter text
            answers: Optional answers to screening questions
        """
        await self._ensure_token()

        # Prepare application data
        application_data = {"cover_letter": cover_letter}
        if answers:
            application_data["answers"] = answers

        try:
            response = await self.client.post(
                f"/resumes/{resume_id}/apply",
                params={"vacancyId": vacancy_id},
                json=application_data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"Application failed for vacancy {vacancy_id}"
            if e.response.status_code == 400:
                error_detail += " - Invalid application data or already applied"
            elif e.response.status_code == 403:
                error_detail += " - Access denied or application not allowed"
            elif e.response.status_code == 404:
                error_detail += " - Vacancy or resume not found"
            else:
                error_detail += f" - HTTP {e.response.status_code}: {e.response.text}"

            raise HTTPException(
                status_code=e.response.status_code,
                detail=error_detail
            )

    async def get_my_resumes(self) -> list[dict]:
        """Get list of user's resumes."""
        await self._ensure_token()
        try:
            response = await self.client.get("/resumes/mine")
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch resumes: {e.response.text}"
            )

    async def get_access_token(self, code: str) -> dict:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
            "code": code,
            "redirect_uri": settings.hh_redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.token_url, data=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Token exchange failed: {e.response.text}"
                )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def get_hh_client() -> HHClient:
    """FastAPI dependency for HH client."""
    client = HHClient()
    try:
        yield client
    finally:
        await client.close()
