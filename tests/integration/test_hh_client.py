"""Integration tests for HH client."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.hh_client import HHClient


class TestHHClientIntegration:
    """Test HH client integration."""

    @pytest.fixture
    async def hh_client(self, mock_hh_token):
        """Create HH client with mocked token."""
        client = HHClient()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_search_vacancies(self, hh_client):
        """Test vacancy search functionality."""
        with patch.object(hh_client, "_make_request") as mock_request:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "items": [{"id": "123", "name": "Developer"}],
                "found": 1,
            }
            mock_request.return_value = mock_response

            result = await hh_client.search_vacancies(text="Python Developer")

            assert "items" in result
            assert len(result["items"]) == 1
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_vacancy_details(self, hh_client):
        """Test getting vacancy details."""
        with patch.object(hh_client, "_make_request") as mock_request:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "id": "123",
                "name": "Python Developer",
                "description": "Job description",
            }
            mock_request.return_value = mock_response

            result = await hh_client.get_vacancy_details("123")

            assert result["id"] == "123"
            assert result["name"] == "Python Developer"

    @pytest.mark.asyncio
    async def test_apply_to_vacancy(self, hh_client):
        """Test applying to vacancy."""
        with patch.object(hh_client, "_make_request") as mock_request:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"status": "ok", "id": "app_123"}
            mock_request.return_value = mock_response

            result = await hh_client.apply(
                vacancy_id="123",
                resume_id="resume_456",
                cover_letter="Cover letter text",
            )

            assert result["status"] == "ok"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, hh_client):
        """Test rate limiting functionality."""
        import time
        start_time = time.time()

        # Simulate multiple rapid requests
        with patch.object(hh_client, "_make_request") as mock_request:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"result": "ok"}
            mock_request.return_value = mock_response

            await hh_client._rate_limit()
            await hh_client._rate_limit()

        # Should take at least the minimum delay
        elapsed = time.time() - start_time
        assert elapsed >= hh_client.REQUEST_DELAY
