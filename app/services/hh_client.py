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
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://hh.ru/",
    "Origin": "https://hh.ru",
}


class HHAPIError(Exception):
    """HH API error."""

    def __init__(
        self, status_code: int, message: str, response_data: dict | None = None
    ):
        self.status_code = status_code
        self.message = message
        self.response_data = response_data or {}
        super().__init__(message)


class HHClient:
    """HeadHunter API client."""

    TOKEN_URL = "https://hh.ru/oauth/token"
    API_BASE = "https://api.hh.ru"

    MAX_REQUESTS_PER_MINUTE = 1000
    REQUEST_DELAY = 0.1

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=self.API_BASE,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._token = None
        self._token_expires_at = None
        self._last_request_time = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _rate_limit(self):
        """Basic rate limiting."""
        if self._last_request_time:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self.REQUEST_DELAY:
                await asyncio.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _ensure_token(self):
        """Ensure we have a valid access token."""
        if (
            self._token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            return

        token = await TokenStorage.get_latest()
        if not token or token.is_expired():
            raise HTTPException(
                status_code=401,
                detail="No valid HH.ru token available. Please re-authenticate via /auth/login",
            )

        self._token = token.access_token
        self._token_expires_at = token.obtained_at + timedelta(
            seconds=token.expires_in - 300
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
    ) -> dict:
        """Make HTTP request with retry logic."""
        kwargs.setdefault("headers", {}).update(DEFAULT_HEADERS)

        await asyncio.sleep(random.uniform(0.5, 2.0))

        await self._ensure_token()
        await self._rate_limit()

        retries = 0
        while True:
            try:
                response = await self.client.request(method, endpoint, **kwargs)

                response_text = (
                    response.text.lower() if hasattr(response, "text") else ""
                )
                if (
                    "ddos-guard" in response_text
                    or "checking your browser" in response_text
                    or response.status_code == 403
                ):
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Request blocked by DDoS protection after {max_retries} retries. "
                            f"Endpoint: {endpoint}, Status: {response.status_code}"
                        )
                        raise HHAPIError(
                            429,
                            "Request blocked by DDoS protection. Please try again later.",
                            {
                                "status_code": response.status_code,
                                "headers": dict(response.headers),
                            },
                        )

                    # Wait longer for DDoS protection
                    delay = base_delay * (2**retries) + random.uniform(2, 5)
                    logger.warning(
                        f"DDoS protection detected. Retry {retries}/{max_retries} after {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code in [502, 503, 504]:
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Gateway error {response.status_code} after {max_retries} retries"
                        )
                        raise HHAPIError(
                            response.status_code,
                            f"Gateway error after {max_retries} retries",
                            {"status_code": response.status_code},
                        )

                    delay = base_delay * (2**retries) + random.uniform(1, 3)
                    logger.warning(
                        f"Gateway error {response.status_code}. Retry {retries}/{max_retries} after {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()

                if not response.text or response.text.strip() == "":
                    return {
                        "status": "success",
                        "status_code": response.status_code,
                    }

                try:
                    return response.json()
                except Exception as e:
                    if response.status_code in [200, 201, 204]:
                        return {
                            "status": "success",
                            "status_code": response.status_code,
                        }
                    logger.error(
                        f"Failed to parse JSON response: {e}, Response text: {response.text[:500]}"
                    )
                    raise HHAPIError(
                        500,
                        f"Invalid JSON response: {e!s}",
                        {"response_text": response.text[:500]},
                    )

            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 and e.response.status_code not in [
                    429,
                    408,
                    502,
                    503,
                    504,
                ]:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except Exception:
                        error_data = {"message": e.response.text[:500]}

                    logger.error(
                        f"HH API client error: {e.response.status_code} - {error_data}, "
                        f"Endpoint: {endpoint}, Method: {method}"
                    )
                    raise HHAPIError(
                        e.response.status_code, str(error_data), error_data
                    )

                retries += 1
                if retries > max_retries:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except Exception:
                        error_data = {"message": e.response.text[:500]}

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
                    logger.error(f"Network error after {max_retries} retries: {e!s}")
                    raise HHAPIError(503, f"Network error: {e!s}")

                delay = base_delay * (2**retries) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"Network error. Retry {retries}/{max_retries} after {delay:.2f}s for {method} {endpoint}"
                )
                await asyncio.sleep(delay)

    async def search_vacancies(
        self,
        text: str | None = None,
        area: int | None = None,
        experience: str | None = None,
        employment: str | None = None,
        schedule: str | None = None,
        salary: int | None = None,
        only_with_salary: bool = False,
        currency: str = "RUR",
        page: int = 0,
        per_page: int = 20,
        **kwargs,
    ) -> dict:
        """Search vacancies with API-level filtering."""
        params = {
            "page": page,
            "per_page": min(per_page, 100),
        }

        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if experience:
            params["experience"] = experience
        if employment:
            params["employment"] = employment
        if schedule:
            params["schedule"] = schedule
        if salary:
            params["salary"] = salary
            params["currency"] = currency
        if only_with_salary:
            params["only_with_salary"] = "true"

        params.update(kwargs)

        try:
            response = await self._make_request("GET", "/vacancies", params=params)
            return response
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Vacancy search failed: {e.message}",
            )

    async def list_vacancies(self, **params) -> dict:
        """Backward compatibility method."""
        return await self.search_vacancies(**params)

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        """Get full vacancy details."""
        try:
            response = await self._make_request("GET", f"/vacancies/{vacancy_id}")
            return response
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
        """Get screening questions for a vacancy."""
        try:
            response = await self._make_request(
                "GET", f"/vacancies/{vacancy_id}/questions"
            )
            return response.get("items", [])
        except HHAPIError as e:
            if e.status_code == 404:
                return []  # No questions for this vacancy
            logger.warning(f"Could not fetch questions for vacancy {vacancy_id}: {e}")
            return []

    async def get_my_resumes(self) -> list[dict]:
        """Get user's resumes."""
        try:
            response = await self._make_request("GET", "/resumes/mine")
            return response.get("items", [])
        except HHAPIError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Failed to fetch resumes: {e.message}",
            )

    async def get_resume_details(self, resume_id: str) -> dict:
        """Get detailed resume information."""
        try:
            response = await self._make_request("GET", f"/resumes/{resume_id}")
            return response
        except HHAPIError as e:
            if e.status_code == 404:
                raise HTTPException(404, f"Resume {resume_id} not found")
            raise HTTPException(e.status_code, f"Failed to fetch resume: {e.message}")

    async def apply(
        self,
        vacancy_id: str,
        resume_id: str,
        cover_letter: str | None = None,
        answers: list[dict] | None = None,
    ) -> dict:
        """Submit application."""
        if cover_letter and cover_letter.strip():
            if len(cover_letter.strip()) < 50:
                raise ValueError("Cover letter must be at least 50 characters long")

        try:
            form_data = {
                "vacancy_id": vacancy_id,
                "resume_id": resume_id,
            }

            if cover_letter and cover_letter.strip():
                form_data["message"] = cover_letter.strip()

            if answers:
                for answer in answers:
                    question_id = answer.get("id")
                    answer_text = answer.get("answer", "")
                    if question_id and answer_text:
                        form_data[f"answer_{question_id}"] = answer_text.strip()
                logger.info(
                    f"Adding {len(answers)} screening question answers to application"
                )

            apply_headers = DEFAULT_HEADERS.copy()
            apply_headers.update(
                {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": f"https://hh.ru/vacancy/{vacancy_id}",
                    "Origin": "https://hh.ru",
                }
            )

            response = await self._make_request(
                "POST", "/negotiations", data=form_data, headers=apply_headers
            )
            logger.info(f"Successfully applied to vacancy {vacancy_id}")
            return response or {"status": "success"}

        except HHAPIError as e:
            error_messages = {
                400: "Invalid application data or already applied to this vacancy",
                403: "Access denied - you may not be eligible for this vacancy",
                404: "Vacancy or resume not found",
                409: "Application already exists for this vacancy",
            }

            error_detail = error_messages.get(
                e.status_code, f"Application failed with HTTP {e.status_code}"
            )

            logger.error(
                f"Application failed for vacancy {vacancy_id}: "
                f"Status {e.status_code}, Response: {e.response_data}"
            )

            raise HTTPException(
                status_code=e.status_code,
                detail=f"Application to vacancy {vacancy_id} failed: {error_detail}",
            )

    async def get_my_applications(self, page: int = 0, per_page: int = 20) -> dict:
        """Get user's job applications history."""
        try:
            response = await self._make_request(
                "GET",
                "/negotiations",
                params={"page": page, "per_page": per_page},
            )
            return response
        except HHAPIError as e:
            raise HTTPException(
                e.status_code, f"Failed to fetch applications: {e.message}"
            )

    async def get_applied_vacancy_ids(self) -> set[str]:
        """Get set of all vacancy IDs user has already applied to."""
        applied_ids = set()
        page = 0
        per_page = 100

        try:
            while True:
                response = await self._make_request(
                    "GET",
                    "/negotiations",
                    params={"page": page, "per_page": per_page},
                )

                items = response.get("items", [])
                if not items:
                    break

                for item in items:
                    vacancy = item.get("vacancy", {})
                    vacancy_id = vacancy.get("id")
                    if vacancy_id:
                        applied_ids.add(str(vacancy_id))

                pages = response.get("pages", 1)
                if page >= pages - 1:
                    break

                page += 1
                await asyncio.sleep(0.5)

                if page >= 20:
                    logger.warning("Reached page limit when fetching applied vacancies")
                    break

            logger.info(
                f"Found {len(applied_ids)} previously applied vacancies from HH.ru"
            )
            return applied_ids

        except HHAPIError as e:
            logger.error(f"Failed to fetch applied vacancies: {e}")
            return set()

    async def get_access_token(self, code: str) -> dict:
        """Exchange authorization code for access token."""
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
                        delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
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
                    detail="Token refresh failed. Please re-authenticate.",
                )

    async def get_areas(self) -> list[dict]:
        """Get available areas (cities/regions)."""
        try:
            response = await self._make_request("GET", "/areas")
            return response
        except HHAPIError as e:
            raise HTTPException(e.status_code, f"Failed to fetch areas: {e.message}")

    async def get_specializations(self) -> list[dict]:
        """Get available job specializations."""
        try:
            response = await self._make_request("GET", "/specializations")
            return response
        except HHAPIError as e:
            raise HTTPException(
                e.status_code, f"Failed to fetch specializations: {e.message}"
            )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_user_info(self, access_token: str) -> dict:
        """Get current user information."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ApplyBot/1.0",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.hh.ru/me", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_user_resumes(self, access_token: str) -> list[dict]:
        """Get user's resumes list."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ApplyBot/1.0",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.hh.ru/resumes/mine", headers=headers
            )
            response.raise_for_status()
            return response.json().get("items", [])

    async def get_resume_details_by_token(
        self, access_token: str, resume_id: str
    ) -> dict:
        """Get detailed resume information by token."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ApplyBot/1.0",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.hh.ru/resumes/{resume_id}", headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def get_user_profile_for_application(
        self, access_token: str, resume_id: str | None = None
    ) -> dict:
        """Get user profile for bulk application."""
        user_info = await self.get_user_info(access_token)
        if not user_info:
            raise ValueError("Failed to get user information")

        resumes = await self.get_user_resumes(access_token)
        if not resumes:
            raise ValueError("User has no resumes on HH.ru")

        if resume_id:
            selected_resume_id = resume_id
        else:
            active_resumes = [
                r for r in resumes if r.get("status", {}).get("id") == "published"
            ]
            selected_resume_id = (
                active_resumes[0]["id"] if active_resumes else resumes[0]["id"]
            )

        resume = await self.get_resume_details_by_token(
            access_token, selected_resume_id
        )
        if not resume:
            raise ValueError("Failed to get resume details")

        def safe_get(data, *keys, default=None):
            """Safely get nested values from a dictionary."""
            result = data
            for key in keys:
                if result is None:
                    return default
                if isinstance(result, dict):
                    result = result.get(key)
                else:
                    return default
            return result if result is not None else default

        profile = {
            "user": {
                "id": user_info.get("id"),
                "email": user_info.get("email"),
                "first_name": user_info.get("first_name"),
                "last_name": user_info.get("last_name"),
                "middle_name": user_info.get("middle_name"),
            },
            "resume": {
                "id": resume.get("id"),
                "title": resume.get("title"),
                "age": resume.get("age"),
                "gender": safe_get(resume, "gender", "name"),
                "area": safe_get(resume, "area", "name"),
                "salary": resume.get("salary"),
                "photo": safe_get(resume, "photo", "medium"),
            },
            "experience": [
                {
                    "company": exp.get("company") or "",
                    "position": exp.get("position") or "",
                    "start": exp.get("start") or "",
                    "end": exp.get("end") or "",
                    "description": exp.get("description") or "",
                }
                for exp in resume.get("experience", [])
                if exp
            ],
            "skills": [
                skill.get("name", "") if isinstance(skill, dict) else str(skill)
                for skill in resume.get("skill_set", [])
                if skill
            ],
            "education": {
                "level": safe_get(resume, "education", "level", "name"),
                "primary": [
                    {
                        "name": edu.get("name") or "",
                        "organization": edu.get("organization") or "",
                        "result": edu.get("result") or "",
                        "year": edu.get("year"),
                    }
                    for edu in resume.get("education", {}).get("primary", [])
                    if edu
                ],
            },
            "languages": [
                {
                    "name": lang.get("name") or "",
                    "level": safe_get(lang, "level", "name") or "",
                }
                for lang in resume.get("language", [])
                if lang
            ],
            "contacts": {
                "phone": next(
                    (
                        c.get("value")
                        for c in resume.get("contact", [])
                        if c and c.get("type", {}).get("id") == "cell"
                    ),
                    None,
                ),
                "email": next(
                    (
                        c.get("value")
                        for c in resume.get("contact", [])
                        if c and c.get("type", {}).get("id") == "email"
                    ),
                    None,
                ),
            },
            "citizenship": [c.get("name") for c in resume.get("citizenship", []) if c],
            "work_ticket": [w.get("name") for w in resume.get("work_ticket", []) if w],
            "travel_time": safe_get(resume, "travel_time", "name"),
            "business_trip_readiness": safe_get(
                resume, "business_trip_readiness", "name"
            ),
            "relocation": safe_get(resume, "relocation", "type", "name"),
        }

        return profile


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
