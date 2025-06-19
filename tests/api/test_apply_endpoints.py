"""Test application endpoints."""

import pytest
from unittest.mock import patch, AsyncMock

from app.schemas.apply import ApplyResponse


class TestApplyEndpoints:
    """Test application API endpoints."""

    @patch("app.routers.apply.get_application_service")
    def test_single_application_endpoint(self, mock_service, test_client, sample_apply_request):
        """Test single application endpoint."""
        mock_service_instance = AsyncMock()
        mock_service_instance.apply_to_single_vacancy.return_value = ApplyResponse(
            vacancy_id="12345",
            status="success",
            vacancy_title="Python Developer",
        )
        mock_service.return_value = mock_service_instance

        response = test_client.post(
            "/apply/single/12345",
            json=sample_apply_request.model_dump(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["vacancy_id"] == "12345"

    @patch("app.routers.apply.get_application_service")
    def test_bulk_application_endpoint(self, mock_service, test_client, sample_bulk_request):
        """Test bulk application endpoint."""
        mock_service_instance = AsyncMock()
        mock_service_instance.bulk_apply.return_value = [
            ApplyResponse(vacancy_id="123", status="success"),
            ApplyResponse(vacancy_id="124", status="error", error_detail="Failed"),
        ]
        mock_service.return_value = mock_service_instance

        response = test_client.post(
            "/apply/bulk?max_applications=10",
            json=sample_bulk_request.model_dump(),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["status"] == "success"

    @patch("app.routers.apply.get_hh_client")
    def test_search_vacancies_endpoint(self, mock_hh_client, test_client):
        """Test vacancy search endpoint."""
        mock_client_instance = AsyncMock()
        mock_client_instance.search_vacancies.return_value = {
            "items": [{"id": "123", "name": "Developer"}],
            "found": 1,
        }
        mock_hh_client.return_value = mock_client_instance

        response = test_client.get("/apply/search?text=Python%20Developer")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1