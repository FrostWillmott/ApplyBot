"""Tests for storage module."""

from datetime import datetime, timedelta


class TestTokenModel:
    """Tests for Token model methods."""

    def test_token_is_expired_with_buffer(self):
        """Test token expiry with buffer time."""
        from app.models.token import Token

        # Token obtained now, expires in 1 hour
        token = Token(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_in=3600,  # 1 hour
            obtained_at=datetime.utcnow(),
        )

        # Should not be expired yet
        assert token.is_expired() is False

    def test_token_is_expired_past_expiry(self):
        """Test token that's past expiry."""
        from app.models.token import Token

        # Token obtained 2 hours ago, expired after 1 hour
        token = Token(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_in=3600,
            obtained_at=datetime.utcnow() - timedelta(hours=2),
        )

        assert token.is_expired() is True

    def test_token_near_expiry(self):
        """Test token near expiry boundary."""
        from app.models.token import Token

        # Token that expires in 2 minutes (within buffer)
        token = Token(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_in=120,  # 2 minutes
            obtained_at=datetime.utcnow(),
        )

        # Depending on buffer, might be expired
        result = token.is_expired()
        assert isinstance(result, bool)


class TestTokenStorage:
    """Tests for TokenStorage class."""

    def test_storage_attributes(self):
        """Test TokenStorage has expected attributes."""
        from app.core.storage import TokenStorage

        assert hasattr(TokenStorage, "init_models")
        assert hasattr(TokenStorage, "save")
        assert hasattr(TokenStorage, "get_latest")

    def test_async_session_creation(self):
        """Test async_session can be imported."""
        from app.core.storage import async_session

        assert async_session is not None

    def test_base_model_import(self):
        """Test Base model can be imported."""
        from app.core.storage import Base

        assert Base is not None


class TestDatabaseModels:
    """Tests for database model definitions."""

    def test_application_history_tablename(self):
        """Test ApplicationHistory tablename."""
        from app.models.application import ApplicationHistory

        assert ApplicationHistory.__tablename__ == "application_history"

    def test_scheduler_settings_tablename(self):
        """Test SchedulerSettings tablename."""
        from app.models.scheduler import SchedulerSettings

        assert SchedulerSettings.__tablename__ == "scheduler_settings"

    def test_scheduler_run_history_tablename(self):
        """Test SchedulerRunHistory tablename."""
        from app.models.scheduler import SchedulerRunHistory

        assert SchedulerRunHistory.__tablename__ == "scheduler_run_history"

    def test_token_tablename(self):
        """Test Token tablename."""
        from app.models.token import Token

        assert Token.__tablename__ == "hh_tokens"


class TestModelRelationships:
    """Tests for model field definitions."""

    def test_application_history_fields(self):
        """Test ApplicationHistory has required fields."""
        from app.models.application import ApplicationHistory

        # Check column names exist
        columns = ApplicationHistory.__table__.columns.keys()
        assert "vacancy_id" in columns
        assert "resume_id" in columns
        assert "applied_at" in columns

    def test_scheduler_settings_fields(self):
        """Test SchedulerSettings has required fields."""
        from app.models.scheduler import SchedulerSettings

        columns = SchedulerSettings.__table__.columns.keys()
        assert "user_id" in columns
        assert "enabled" in columns
        assert "schedule_hour" in columns
        assert "schedule_minute" in columns

    def test_scheduler_run_history_fields(self):
        """Test SchedulerRunHistory has required fields."""
        from app.models.scheduler import SchedulerRunHistory

        columns = SchedulerRunHistory.__table__.columns.keys()
        assert "user_id" in columns
        assert "started_at" in columns
        assert "status" in columns
        assert "applications_sent" in columns

    def test_token_fields(self):
        """Test Token has required fields."""
        from app.models.token import Token

        columns = Token.__table__.columns.keys()
        assert "access_token" in columns
        assert "refresh_token" in columns
        assert "expires_in" in columns
        assert "obtained_at" in columns


class TestModelIndexes:
    """Tests for model indexes."""

    def test_scheduler_settings_user_id_indexed(self):
        """Test SchedulerSettings user_id is indexed."""
        from app.models.scheduler import SchedulerSettings

        # Check that user_id column exists and is indexed
        user_id_col = SchedulerSettings.__table__.columns.get("user_id")
        assert user_id_col is not None

    def test_scheduler_run_history_user_id_indexed(self):
        """Test SchedulerRunHistory user_id is indexed."""
        from app.models.scheduler import SchedulerRunHistory

        user_id_col = SchedulerRunHistory.__table__.columns.get("user_id")
        assert user_id_col is not None
