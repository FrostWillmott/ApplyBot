"""Integration tests for application service."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.application_service import ApplicationService


class TestApplicationServiceIntegration:
    """Test application service integration."""

    @pytest.fixture
    def application_service(self, mock_hh_client, mock_llm_provider):
        """Create application service with mocked dependencies."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.mark.asyncio
    async def test_single_application_success(
            self, application_service, sample_apply_request, sample_vacancy
    ):
        """Test successful single application."""
        # Mock the service methods
        application_service.hh_client.get_vacancy_details.return_value = sample_vacancy
        application_service.llm_provider.generate_cover_letter.return_value = "Cover letter"
        application_service.hh_client.apply.return_value = {"status": "ok"}

        with patch.object(application_service, "_has_already_applied", return_value=False):
            with patch.object(application_service, "_can_apply_to_vacancy", return_value=(True, "")):
                result = await application_service.apply_to_single_vacancy(
                    "12345", sample_apply_request
                )

        assert result.status == "success"
        assert result.vacancy_id == "12345"

    @pytest.mark.asyncio
    async def test_bulk_application(
            self, application_service, sample_bulk_request
    ):
        """Test bulk application functionality."""
        # Mock search results
        mock_vacancies = [
            {"id": "123", "name": "Python Dev", "employer": {"name": "TechCorp"}},
            {"id": "124", "name": "Backend Dev", "employer": {"name": "StartupCorp"}},
        ]

        application_service.hh_client.search_vacancies.return_value = {
            "items": mock_vacancies
        }

        with patch.object(application_service, "apply_to_single_vacancy") as mock_apply:
            mock_apply.return_value = AsyncMock(status="success", vacancy_id="123")

            results = await application_service.bulk_apply(
                sample_bulk_request, max_applications=5
            )

        assert len(results) >= 1
        assert all(hasattr(result, "status") for result in results)
