"""Tests for bulk application logic in ApplicationService."""

import unittest
from unittest.mock import AsyncMock

import pytest

from app.schemas.apply import BulkApplyRequest
from app.services.application_service import ApplicationService


class TestBulkApply:
    """Tests for bulk_apply method."""

    @pytest.fixture(autouse=True)
    def mock_sleep(self):
        """Mock asyncio.sleep to avoid waiting during tests."""
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def service(self, mock_hh_client, mock_llm_provider):
        """Create ApplicationService instance."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.fixture
    def bulk_request(self):
        """Create sample bulk apply request."""
        return BulkApplyRequest(
            position="Python Developer",
            experience_level="middle",
            salary_min=100000,
            use_cover_letter=True,
            resume_id="resume_123",
        )

    @pytest.fixture
    def mock_vacancy(self):
        return {"id": "vac_1", "name": "Python Dev", "archived": False, "relations": []}

    @pytest.mark.asyncio
    async def test_bulk_apply_success(self, service, bulk_request, mock_vacancy):
        """Test successful bulk application run."""
        # Mock dependencies
        service.hh_client.get_applied_vacancy_ids = AsyncMock(return_value=[])
        service.hh_client.search_vacancies = AsyncMock(
            side_effect=[
                {"items": [mock_vacancy], "found": 1},
                {"items": [], "found": 1},
            ]
        )
        service.hh_client.get_vacancy_details = AsyncMock(return_value=mock_vacancy)
        service.hh_client.get_resume_details = AsyncMock(
            return_value={
                "experience": [],
                "skill_set": [],
                "education": {"items": []},
                "description": "Resume",
                "title": "Dev",
            }
        )
        service.hh_client.apply = AsyncMock(return_value={"url": "http://hh.ru/appl/1"})

        # Mock DB methods
        service._has_already_applied = AsyncMock(return_value=False)
        service._record_application = AsyncMock()

        results = await service.bulk_apply(bulk_request, max_applications=1)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].vacancy_id == "vac_1"

    @pytest.mark.asyncio
    async def test_bulk_apply_skips_already_applied(
        self, service, bulk_request, mock_vacancy
    ):
        """Test that bulk apply skips vacancies already applied to."""
        service.hh_client.get_applied_vacancy_ids = AsyncMock(return_value=["vac_1"])
        service.hh_client.search_vacancies = AsyncMock(
            side_effect=[
                {"items": [mock_vacancy], "found": 1},
                {"items": [], "found": 1},
            ]
        )
        # Mock DB methods
        service._has_already_applied = AsyncMock(
            return_value=False
        )  # HH says applied, so this might not be called, but good to mock
        service._record_application = AsyncMock()

        results = await service.bulk_apply(bulk_request, max_applications=1)

        assert len(results) == 1
        assert results[0].status == "skipped"
        assert "Already applied" in results[0].error_detail

    @pytest.mark.asyncio
    async def test_bulk_apply_handles_error_gracefully(
        self, service, bulk_request, mock_vacancy
    ):
        """Test that single application failure doesn't crash bulk process."""
        service.hh_client.get_applied_vacancy_ids = AsyncMock(return_value=[])
        # Two vacancies
        vac1 = {**mock_vacancy, "id": "vac_1"}
        vac2 = {**mock_vacancy, "id": "vac_2"}

        service.hh_client.search_vacancies = AsyncMock(
            side_effect=[{"items": [vac1, vac2], "found": 2}, {"items": [], "found": 2}]
        )
        service.hh_client.get_vacancy_details = AsyncMock(side_effect=[vac1, vac2])
        service.hh_client.get_resume_details = AsyncMock(return_value={})

        # First fails, second succeeds
        service.hh_client.apply = AsyncMock(
            side_effect=[Exception("Network error"), {"url": "ok"}]
        )

        # Mock DB methods
        service._has_already_applied = AsyncMock(return_value=False)
        service._record_application = AsyncMock()

        results = await service.bulk_apply(bulk_request, max_applications=2)

        assert len(results) == 2
        assert results[0].status == "error"
        assert results[1].status == "success"

    @pytest.mark.asyncio
    async def test_bulk_apply_circuit_breaker(
        self, service, bulk_request, mock_vacancy
    ):
        """Test that circuit breaker stops execution after too many errors."""
        service.hh_client.get_applied_vacancy_ids = AsyncMock(return_value=[])
        # 5 vacancies
        vacancies = [{**mock_vacancy, "id": f"vac_{i}"} for i in range(5)]

        service.hh_client.search_vacancies = AsyncMock(
            return_value={"items": vacancies, "found": 5}
        )
        service.hh_client.get_vacancy_details = AsyncMock(return_value=mock_vacancy)
        service.hh_client.get_resume_details = AsyncMock(return_value={})

        # All fail
        service.hh_client.apply = AsyncMock(side_effect=Exception("Repeated failure"))

        # Mock DB methods and applied check - fix greenlet error here too!
        service._has_already_applied = AsyncMock(return_value=False)
        service._record_application = AsyncMock()

        # Max errors is 3 in code
        results = await service.bulk_apply(bulk_request, max_applications=5)

        # Should stop after 3 errors
        assert len(results) == 3
        assert all(r.status == "error" for r in results)

    @pytest.mark.asyncio
    async def test_bulk_apply_empty_search(self, service, bulk_request):
        """Test empty search results."""
        service.hh_client.get_applied_vacancy_ids = AsyncMock(return_value=[])
        service.hh_client.search_vacancies = AsyncMock(
            return_value={"items": [], "found": 0}
        )

        results = await service.bulk_apply(bulk_request)
        assert len(results) == 0
