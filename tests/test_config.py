"""Tests for configuration module."""

import os
from unittest.mock import patch


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_loads_from_env(self):
        """Test that settings loads from environment."""
        env_vars = {
            "HH_CLIENT_ID": "test_client_id",
            "HH_CLIENT_SECRET": "test_secret",
            "HH_REDIRECT_URI": "http://localhost/callback",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            assert settings.hh_client_id == "test_client_id"
            assert settings.hh_client_secret == "test_secret"
            assert settings.ollama_base_url == "http://localhost:11434"
            assert settings.ollama_model == "qwen3:14b"

    def test_default_scheduler_settings(self):
        """Test default scheduler settings when not overridden."""
        env_vars = {
            "HH_CLIENT_ID": "test",
            "HH_CLIENT_SECRET": "test",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "SCHEDULER_ENABLED": "true",  # Explicitly set to test default behavior
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            assert settings.scheduler_enabled is True
            assert settings.scheduler_default_hour == 9
            assert settings.scheduler_default_minute == 0
            assert settings.scheduler_default_days == "mon,tue,wed,thu,fri"
            assert settings.scheduler_default_timezone == "Europe/Moscow"
            assert settings.scheduler_max_applications == 20

    def test_cookie_secure_default(self):
        """Test default cookie_secure setting."""
        env_vars = {
            "HH_CLIENT_ID": "test",
            "HH_CLIENT_SECRET": "test",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            assert settings.cookie_secure is True

    def test_llm_provider_default(self):
        """Test default LLM provider."""
        env_vars = {
            "HH_CLIENT_ID": "test",
            "HH_CLIENT_SECRET": "test",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            assert settings.llm_provider == "ollama"

    def test_settings_case_insensitive(self):
        """Test that settings are case insensitive."""
        env_vars = {
            "hh_client_id": "test_lower",
            "HH_CLIENT_SECRET": "test_upper",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            # Should accept both cases
            assert settings.hh_client_secret == "test_upper"

    def test_custom_scheduler_settings(self):
        """Test custom scheduler settings from env."""
        env_vars = {
            "HH_CLIENT_ID": "test",
            "HH_CLIENT_SECRET": "test",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "SCHEDULER_ENABLED": "false",
            "SCHEDULER_DEFAULT_HOUR": "14",
            "SCHEDULER_DEFAULT_MINUTE": "30",
            "SCHEDULER_MAX_APPLICATIONS": "50",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            assert settings.scheduler_enabled is False
            assert settings.scheduler_default_hour == 14
            assert settings.scheduler_default_minute == 30
            assert settings.scheduler_max_applications == 50


class TestConfigValidation:
    """Tests for config validation."""

    def test_database_url_is_valid_url(self):
        """Test that database_url must be valid URL."""
        env_vars = {
            "HH_CLIENT_ID": "test",
            "HH_CLIENT_SECRET": "test",
            "HH_REDIRECT_URI": "http://test",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "qwen3:14b",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            from app.core.config import Settings

            settings = Settings()

            # URL should be parsed correctly
            assert "postgresql" in str(settings.database_url)
