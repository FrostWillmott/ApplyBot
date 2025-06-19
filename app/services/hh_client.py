import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.storage import TokenStorage

logger = logging.getLogger(__name__)


class HHAPIError(Exception):
    """Custom exception for HH API errors"""
    def __init__(self, status_code: int, message: str, response_data: dict = None):
        self.status_code = status_code
        self.message = message
        self.response_data = response_data or {}
        super().__init__(message)


class HHClient:
    """Enhanced HeadHunter API client with improved error handling and caching."""

    TOKEN_URL = "https://hh.ru/oauth/token"
    API_BASE = "https://api.hh.ru"

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 1000  # HH API limit
    REQUEST_DELAY = 0.1  # Minimum delay between requests

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=self.API_BASE,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        self._token = None
        self._token_expires_at = None
        self._last_request_time = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _rate_limit(self):
        """Implement basic rate limiting"""
        if self._last_request_time:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self.REQUEST_DELAY:
                await asyncio.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _ensure_token(self):
        """Ensure we have a valid access token with improved caching."""
        # Check if we have a cached valid token
        if (self._token and self._token_expires_at and
                datetime.utcnow() < self._token_expires_at):
            return

        # Get token from database
        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            raise HTTPException(
                status_code=401,
                detail="No valid HH.ru token available. Please re-authenticate via /auth/login"
            )

        self._token = token.access_token
        # Cache token expiration (with 5 minute buffer)
        self._token_expires_at = (
                token.obtained_at + timedelta(seconds=token.expires_in - 300)
        )

        self.client.headers.update({"Authorization": f"Bearer {self._token}"})
        logger.info("HH token refreshed successfully")

    async def _make_request(
            self,
            method: str,
            endpoint: str,
            **kwargs
    ) -> httpx.Response:
        """Make HTTP request with error handling and rate limiting."""
        await self._ensure_token()
        await self._rate_limit()

        try:
            response = await self.client.request(method, endpoint, **kwargs)

            # Enhanced error handling
            if response.status_code == 429:
                # Rate limit exceeded
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                await asyncio.sleep(retry_after)
                return await self._make_request(method, endpoint, **kwargs)

            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except:
                error_data = {"message": e.response.text}

            logger.error(f"HH API error: {e.response.status_code} - {error_data}")
            raise HHAPIError(e.response.status_code, str(error_data), error_data)

    # Vacancy Management
    async def search_vacancies(
            self,
            text: str = None,
            area: int = None,
            experience: str = None,
            employment: str = None,
            salary: int = None,
            currency: str = "RUR",
            page: int = 0,
            per_page: int = 20,
            **kwargs
    ) -> dict:
        """Enhanced vacancy search with better parameter handling."""
        params = {
            "page": page,
            "per_page": min(per_page, 100)  # HH API limit
        }

        # Add optional parameters
        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if experience:
            params["experience"] = experience
        if employment:
            params["employment"] = employment
        if salary:
            params["salary"] = salary
            params["currency"] = currency

        # Add any additional parameters
        params.update(kwargs)

        try:
            response = await self._make_request("GET", "/vacancies", params=params)
            return response.json()
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Vacancy search failed: {e.message}"
            )

    # Maintain backward compatibility
    async def list_vacancies(self, **params) -> dict:
        """Backward compatibility method."""
        return await self.search_vacancies(**params)

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        """Get full vacancy details with caching potential."""
        try:
            response = await self._make_request("GET", f"/vacancies/{vacancy_id}")
            return response.json()
        except HHAPIError as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Vacancy {vacancy_id} not found"
                )
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch vacancy: {e.message}"
            )

    async def get_vacancy_questions(self, vacancy_id: str) -> list[dict]:
        """Get screening questions with improved structure."""
        try:
            response = await self._make_request("GET", f"/vacancies/{vacancy_id}/questions")
            data = response.json()
            return data.get("items", [])
        except HHAPIError as e:
            if e.status_code == 404:
                return []  # No questions for this vacancy
            logger.warning(f"Could not fetch questions for vacancy {vacancy_id}: {e}")
            return []

    # Resume Management
    async def get_my_resumes(self) -> list[dict]:
        """Get user's resumes with better error handling."""
        try:
            response = await self._make_request("GET", "/resumes/mine")
            data = response.json()
            return data.get("items", [])
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch resumes: {e.message}"
            )

    async def get_resume_details(self, resume_id: str) -> dict:
        """Get detailed resume information."""
        try:
            response = await self._make_request("GET", f"/resumes/{resume_id}")
            return response.json()
        except HHAPIError as e:
            if e.status_code == 404:
                raise HTTPException(404, f"Resume {resume_id} not found")
            raise HTTPException(e.status_code, f"Failed to fetch resume: {e.message}")

    # Application Management
    async def apply(
            self,
            vacancy_id: str,
            resume_id: str,
            cover_letter: str,
            answers: list[dict] | None = None
    ) -> dict:
        """Submit application with enhanced validation."""
        if not cover_letter.strip():
            raise ValueError("Cover letter cannot be empty")

        application_data = {
            "cover_letter": cover_letter.strip()
        }

        if answers:
            # Validate answers format
            for answer in answers:
                if "id" not in answer or "answer" not in answer:
                    raise ValueError("Invalid answer format. Expected {id, answer}")
            application_data["answers"] = answers

        try:
            response = await self._make_request(
                "POST",
                f"/resumes/{resume_id}/apply",
                params={"vacancyId": vacancy_id},
                json=application_data
            )
            logger.info(f"Successfully applied to vacancy {vacancy_id}")
            return response.json()

        except HHAPIError as e:
            error_messages = {
                400: "Invalid application data or already applied to this vacancy",
                403: "Access denied - you may not be eligible for this vacancy",
                404: "Vacancy or resume not found",
                409: "Application already exists for this vacancy"
            }

            error_detail = error_messages.get(
                e.status_code,
                f"Application failed with HTTP {e.status_code}"
            )

            raise HTTPException(
                status_code=e.status_code,
                detail=f"Application to vacancy {vacancy_id} failed: {error_detail}"
            )

    async def get_my_applications(self, page: int = 0, per_page: int = 20) -> dict:
        """Get user's job applications history."""
        try:
            response = await self._make_request(
                "GET",
                "/negotiations",
                params={"page": page, "per_page": per_page}
            )
            return response.json()
        except HHAPIError as e:
            raise HTTPException(e.status_code, f"Failed to fetch applications: {e.message}")

    # OAuth Management
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
                response = await client.post(self.TOKEN_URL, data=data)
                response.raise_for_status()
                token_data = response.json()
                token_data["obtained_at"] = datetime.utcnow()
                return token_data
            except httpx.HTTPStatusError as e:
                logger.error(f"Token exchange failed: {e.response.text}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Token exchange failed: {e.response.text}"
                )

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
                response.raise_for_status()
                token_data = response.json()
                token_data["obtained_at"] = datetime.utcnow()
                return token_data
            except httpx.HTTPStatusError as e:
                logger.error(f"Token refresh failed: {e.response.text}")
                raise HTTPException(
                    status_code=400,
                    detail="Token refresh failed. Please re-authenticate."
                )

    # Utility Methods
    async def get_areas(self) -> list[dict]:
        """Get available areas (cities/regions)."""
        try:
            response = await self._make_request("GET", "/areas")
            return response.json()
        except HHAPIError as e:
            raise HTTPException(e.status_code, f"Failed to fetch areas: {e.message}")

    async def get_specializations(self) -> list[dict]:
        """Get available job specializations."""
        try:
            response = await self._make_request("GET", "/specializations")
            return response.json()
        except HHAPIError as e:
            raise HTTPException(e.status_code, f"Failed to fetch specializations: {e.message}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# FastAPI Dependencies
async def get_hh_client():
    """FastAPI dependency for HH client with proper cleanup."""
    client = HHClient()
    try:
        yield client
    finally:
        await client.close()


async def get_hh_client_context():
    """Context manager version for use in services."""
    async with HHClient() as client:
        return client
