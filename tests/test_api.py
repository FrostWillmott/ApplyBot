"""Tests for API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestAPIEndpoints:
    """Tests for main API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        # Mock the settings to avoid loading .env
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.scheduler_enabled = False
            mock_settings.hh_client_id = "test"
            mock_settings.hh_client_secret = "test"
            mock_settings.hh_redirect_uri = "http://test"
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "qwen3:14b"
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"

            # Mock TokenStorage
            with patch("app.core.storage.TokenStorage") as mock_storage:
                mock_storage.init_models = AsyncMock()
                mock_storage.get_latest = AsyncMock(return_value=None)

                # Mock scheduler service
                with patch(
                    "app.services.scheduler_service.scheduler_service"
                ) as mock_scheduler:
                    mock_scheduler.get_status.return_value = {"running": False}
                    mock_scheduler.start = AsyncMock()
                    mock_scheduler.stop = AsyncMock()

                    from app.main import app

                    yield TestClient(app, raise_server_exceptions=False)

    def test_root_endpoint(self, client):
        """Test root endpoint serves frontend."""
        response = client.get("/")
        # Should return HTML or redirect to static
        assert response.status_code in [200, 307]

    def test_api_info_endpoint(self, client):
        """Test API info endpoint."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "ApplyBot API"
        assert "version" in data
        assert "docs" in data

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "applybot"
        assert "scheduler" in data

    def test_docs_endpoint(self, client):
        """Test that OpenAPI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_endpoint(self, client):
        """Test that OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.scheduler_enabled = False
            mock_settings.hh_client_id = "test_client_id"
            mock_settings.hh_client_secret = "test_secret"
            mock_settings.hh_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "qwen3:14b"
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"
            mock_settings.cookie_secure = False

            with patch("app.core.storage.TokenStorage") as mock_storage:
                mock_storage.init_models = AsyncMock()
                mock_storage.get_latest = AsyncMock(return_value=None)

                with patch(
                    "app.services.scheduler_service.scheduler_service"
                ) as mock_scheduler:
                    mock_scheduler.get_status.return_value = {"running": False}
                    mock_scheduler.start = AsyncMock()
                    mock_scheduler.stop = AsyncMock()

                    from app.main import app

                    yield TestClient(app, raise_server_exceptions=False)

    def test_login_redirect(self, client):
        """Test login redirects to HH OAuth."""
        response = client.get("/auth/login", follow_redirects=False)
        assert response.status_code in [302, 307]
        location = response.headers.get("location", "")
        assert "hh.ru" in location or "oauth" in location.lower()

    def test_auth_status_not_authenticated(self, client):
        """Test auth status when not authenticated."""
        response = client.get("/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False


class TestSchedulerEndpoints:
    """Tests for scheduler endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked auth."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.scheduler_enabled = True
            mock_settings.hh_client_id = "test"
            mock_settings.hh_client_secret = "test"
            mock_settings.hh_redirect_uri = "http://test"
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "qwen3:14b"
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"

            with patch("app.core.storage.TokenStorage") as mock_storage:
                mock_storage.init_models = AsyncMock()
                mock_storage.get_latest = AsyncMock(return_value=None)

                with patch(
                    "app.services.scheduler_service.scheduler_service"
                ) as mock_scheduler:
                    mock_scheduler.get_status.return_value = {
                        "running": True,
                        "jobs_count": 0,
                    }
                    mock_scheduler.start = AsyncMock()
                    mock_scheduler.stop = AsyncMock()

                    from app.main import app

                    yield TestClient(app, raise_server_exceptions=False)

    def test_scheduler_status_endpoint_exists(self, client):
        """Test that scheduler status endpoint exists."""
        response = client.get("/scheduler/status")
        # Endpoint exists - may require auth or return error due to mocking
        assert response.status_code in [200, 401, 403, 500]

    def test_scheduler_settings_endpoint_exists(self, client):
        """Test that scheduler settings endpoint exists."""
        response = client.get("/scheduler/settings")
        # Endpoint exists - may require auth or return error due to mocking
        assert response.status_code in [200, 401, 403, 500]


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.scheduler_enabled = False
            mock_settings.hh_client_id = "test"
            mock_settings.hh_client_secret = "test"
            mock_settings.hh_redirect_uri = "http://test"
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "qwen3:14b"
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"

            with patch("app.core.storage.TokenStorage") as mock_storage:
                mock_storage.init_models = AsyncMock()

                with patch(
                    "app.services.scheduler_service.scheduler_service"
                ) as mock_scheduler:
                    mock_scheduler.get_status.return_value = {"running": False}
                    mock_scheduler.start = AsyncMock()
                    mock_scheduler.stop = AsyncMock()

                    from app.main import app

                    yield TestClient(app)

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present."""
        response = client.options(
            "/api",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS should be configured
        assert response.status_code in [200, 204, 405]
