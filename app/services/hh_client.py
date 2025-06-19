import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.storage import TokenStorage

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'Upgrade-Insecure-Requests': '1',
}


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
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs,
    ) -> dict:  # Changed return type to dict
        """Make HTTP request with error handling, rate limiting, and exponential backoff."""
        kwargs.setdefault("headers", {}).update(DEFAULT_HEADERS)

        await asyncio.sleep(random.uniform(0.5, 2.0))

        await self._ensure_token()
        await self._rate_limit()

        retries = 0
        while True:
            try:
                response = await self.client.request(
                    method, endpoint, **kwargs
                )

                # Check for DDoS protection page
                if (
                    "ddos-guard" in response.text.lower()
                    or "checking your browser" in response.text.lower()
                ):
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            "Request blocked by DDoS protection after all retries"
                        )
                        raise HHAPIError(
                            429,
                            "Request blocked by DDoS protection. Please try again later.",
                        )

                    # Wait longer for DDoS protection
                    delay = base_delay * (2**retries) + random.uniform(2, 5)
                    logger.warning(
                        f"DDoS protection detected. Retry {retries}/{max_retries} after {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Rate limited. Waiting {retry_after} seconds"
                    )
                    await asyncio.sleep(retry_after)
                    continue

                # Handle 502/503 Bad Gateway errors (common with DDoS protection)
                if response.status_code in [502, 503, 504]:
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Gateway error {response.status_code} after {max_retries} retries"
                        )
                        raise HHAPIError(
                            response.status_code,
                            f"Gateway error after {max_retries} retries",
                        )

                    delay = base_delay * (2**retries) + random.uniform(1, 3)
                    logger.warning(
                        f"Gateway error {response.status_code}. Retry {retries}/{max_retries} after {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Success case
                response.raise_for_status()
                return response.json()  # Return the JSON directly

            except httpx.HTTPStatusError as e:
                # Don't retry for client errors (4xx) except specific ones
                if (
                    e.response.status_code < 500
                    and e.response.status_code not in [429, 408, 502, 503, 504]
                ):
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        error_data = {"message": e.response.text}

                    logger.error(
                        f"HH API client error: {e.response.status_code} - {error_data}"
                    )
                    raise HHAPIError(
                        e.response.status_code, str(error_data), error_data
                    )

                # For server errors, use exponential backoff
                retries += 1
                if retries > max_retries:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        error_data = {"message": e.response.text}

                    logger.error(
                        f"HH API error after {max_retries} retries: {e.response.status_code} - {error_data}"
                    )
                    raise HHAPIError(
                        e.response.status_code, str(error_data), error_data
                    )

                delay = base_delay * (2**retries) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"Server error. Retry {retries}/{max_retries} after {delay:.2f}s for {method} {endpoint}"
                )
                await asyncio.sleep(delay)

            except (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ) as e:
                retries += 1
                if retries > max_retries:
                    logger.error(
                        f"Network error after {max_retries} retries: {str(e)}"
                    )
                    raise HHAPIError(503, f"Network error: {str(e)}")

                delay = base_delay * (2**retries) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"Network error. Retry {retries}/{max_retries} after {delay:.2f}s for {method} {endpoint}"
                )
                await asyncio.sleep(delay)

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
        **kwargs,
    ) -> dict:
        """Enhanced vacancy search with better parameter handling."""
        params = {
            "page": page,
            "per_page": min(per_page, 100),  # HH API limit
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
            response = await self._make_request(
                "GET", "/vacancies", params=params
            )
            return response  # _make_request already returns JSON
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Vacancy search failed: {e.message}",
            )

    # Maintain backward compatibility
    async def list_vacancies(self, **params) -> dict:
        """Backward compatibility method."""
        return await self.search_vacancies(**params)

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        """Get full vacancy details with caching potential."""
        try:
            response = await self._make_request(
                "GET", f"/vacancies/{vacancy_id}"
            )
            return response  # _make_request already returns JSON
        except HHAPIError as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"Vacancy {vacancy_id} not found"
                )
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch vacancy: {e.message}",
            )

    async def get_vacancy_questions(self, vacancy_id: str) -> list[dict]:
        """Get screening questions with improved structure."""
        try:
            response = await self._make_request(
                "GET", f"/vacancies/{vacancy_id}/questions"
            )
            return response.get("items", [])  # response is already JSON
        except HHAPIError as e:
            if e.status_code == 404:
                return []  # No questions for this vacancy
            logger.warning(
                f"Could not fetch questions for vacancy {vacancy_id}: {e}"
            )
            return []

    async def get_my_resumes(self) -> list[dict]:
        """Get user's resumes with better error handling."""
        try:
            response = await self._make_request("GET", "/resumes/mine")
            return response.get("items", [])  # response is already JSON
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch resumes: {e.message}",
            )

    async def get_resume_details(self, resume_id: str) -> dict:
        """Get detailed resume information."""
        try:
            response = await self._make_request("GET", f"/resumes/{resume_id}")
            return response  # _make_request already returns JSON
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
        """Exchange authorization code for access token with retry logic."""
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
            "code": code,
            "redirect_uri": settings.hh_redirect_uri,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://hh.ru",
            "Referer": "https://hh.ru/",
        }

        max_retries = 3
        base_delay = 2.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        # Exponential backoff with jitter
                        delay = base_delay * (
                            2 ** (attempt - 1)
                        ) + random.uniform(0, 1)
                        logger.info(
                            f"Token exchange retry {attempt}/{max_retries} after {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)

                    response = await client.post(
                        self.TOKEN_URL, data=data, headers=headers
                    )

                    # Check if we got DDoS protection page
                    if "ddos-guard" in response.text.lower():
                        if attempt < max_retries:
                            logger.warning(
                                f"DDoS protection detected, retrying... ({attempt + 1}/{max_retries + 1})"
                            )
                            continue
                        else:
                            raise HTTPException(
                                status_code=429,
                                detail="Request blocked by DDoS protection. Please try again later.",
                            )

                    response.raise_for_status()
                    token_data = response.json()
                    token_data["obtained_at"] = datetime.utcnow()
                    return token_data

                except httpx.HTTPStatusError as e:
                    if attempt < max_retries and e.response.status_code >= 500:
                        continue
                    logger.error(f"Token exchange failed: {e.response.text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Token exchange failed: {e.response.text}",
                    )

            raise HTTPException(
                status_code=429,
                detail="Token exchange failed after all retry attempts",
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
