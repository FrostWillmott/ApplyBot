"""Test authentication endpoints."""
import time
from unittest.mock import AsyncMock, patch
from app.schemas.apply import BulkApplyRequest

class TestAuthEndpoints:
    """Test authentication API endpoints."""

    def test_login_redirect(self, test_client):
        """Test login endpoint redirects to HH OAuth."""
        response = test_client.get("/auth/login")
        assert response.status_code == 307  # Redirect
        assert "hh.ru/oauth/authorize" in response.headers["location"]

    @patch("app.routers.auth.HHClient")
    def test_oauth_callback_success(self, mock_hh_client, test_client):
        """Test successful OAuth callback."""
        # Setup mock OAuth response
        mock_oauth_response = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get_access_token.return_value = mock_oauth_response
        mock_hh_client.return_value = mock_client_instance

        # Test OAuth callback endpoint
        response = test_client.get("/auth/callback?code=test_code")

        assert response.status_code == 200
        mock_client_instance.get_access_token.assert_called_once()

    @patch("app.services.application_service")
    def test_bulk_apply_performance(self, mock_service):
        """Test bulk application performance and limits."""
        # Setup test data
        bulk_request = self._create_bulk_apply_request()
        max_applications = 50

        # Setup mock service
        mock_apply_result = AsyncMock(status="success", vacancy_id="123")
        mock_service.apply_to_single_vacancy.return_value = mock_apply_result

        # Measure performance
        start_time = time.time()
        results = self._execute_bulk_apply(mock_service, bulk_request, max_applications)
        end_time = time.time()

        # Verify results
        assert len(results) <= max_applications
        assert end_time - start_time < 10.0  # Should complete within reasonable time

    def _create_bulk_apply_request(self):
        """Create a test bulk apply request."""
        return BulkApplyRequest(
            position="Developer",
            resume="Resume content",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
        )

    async def _execute_bulk_apply(self, service, request, max_applications):
        """Execute bulk apply with proper async handling."""
        return await service.bulk_apply(request, max_applications=max_applications)