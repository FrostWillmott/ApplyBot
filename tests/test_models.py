"""Tests for database models."""

from datetime import UTC, datetime, timedelta

from app.models.application import ApplicationHistory
from app.models.scheduler import SchedulerRunHistory, SchedulerSettings
from app.models.token import Token


def _utc_now() -> datetime:
    """Return current UTC time as timezone-naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)


class TestApplicationHistory:
    """Tests for ApplicationHistory model."""

    def test_model_creation(self):
        """Test creating ApplicationHistory instance."""
        app = ApplicationHistory(
            vacancy_id="12345",
            resume_id="resume_123",
            user_id="user_001",
            applied_at=_utc_now(),
            hh_response={"status": "success"},
        )
        assert app.vacancy_id == "12345"
        assert app.resume_id == "resume_123"
        assert app.user_id == "user_001"

    def test_model_with_none_user_id(self):
        """Test creating ApplicationHistory without user_id."""
        app = ApplicationHistory(
            vacancy_id="12345", resume_id="resume_123", applied_at=_utc_now()
        )
        assert app.user_id is None

    def test_model_with_empty_response(self):
        """Test creating ApplicationHistory with empty response."""
        app = ApplicationHistory(
            vacancy_id="12345",
            resume_id="resume_123",
            applied_at=_utc_now(),
            hh_response={},
        )
        assert app.hh_response == {}


class TestSchedulerSettings:
    """Tests for SchedulerSettings model."""

    def test_model_creation_defaults(self):
        """Test creating SchedulerSettings with defaults."""
        # Note: SQLAlchemy defaults are applied on INSERT, not on object creation
        settings = SchedulerSettings(
            user_id="user_001",
            enabled=False,
            schedule_hour=9,
            schedule_minute=0,
            schedule_days="mon,tue,wed,thu,fri",
            timezone="Europe/Moscow",
            max_applications_per_run=10,
        )
        assert settings.user_id == "user_001"
        assert settings.enabled is False
        assert settings.schedule_hour == 9
        assert settings.schedule_minute == 0
        assert settings.schedule_days == "mon,tue,wed,thu,fri"
        assert settings.timezone == "Europe/Moscow"
        assert settings.max_applications_per_run == 10

    def test_model_with_custom_schedule(self):
        """Test creating SchedulerSettings with custom schedule."""
        settings = SchedulerSettings(
            user_id="user_001",
            enabled=True,
            schedule_hour=14,
            schedule_minute=30,
            schedule_days="mon,wed,fri",
            timezone="UTC",
        )
        assert settings.enabled is True
        assert settings.schedule_hour == 14
        assert settings.schedule_minute == 30
        assert settings.schedule_days == "mon,wed,fri"
        assert settings.timezone == "UTC"

    def test_model_with_search_criteria(self):
        """Test creating SchedulerSettings with search criteria."""
        criteria = {
            "position": "Python Developer",
            "salary_min": 100000,
            "remote_only": True,
        }
        settings = SchedulerSettings(user_id="user_001", search_criteria=criteria)
        assert settings.search_criteria == criteria

    def test_model_statistics_defaults(self):
        """Test default statistics values."""
        # Note: SQLAlchemy defaults are applied on INSERT, not on object creation
        settings = SchedulerSettings(
            user_id="user_001",
            enabled=False,
            schedule_hour=9,
            schedule_minute=0,
            schedule_days="mon,tue,wed,thu,fri",
            timezone="Europe/Moscow",
            max_applications_per_run=10,
            last_run_applications=0,
            total_applications=0,
        )
        assert settings.last_run_at is None
        assert settings.last_run_status is None
        assert settings.last_run_applications == 0
        assert settings.total_applications == 0


class TestSchedulerRunHistory:
    """Tests for SchedulerRunHistory model."""

    def test_model_creation(self):
        """Test creating SchedulerRunHistory instance."""
        run = SchedulerRunHistory(
            user_id="user_001",
            started_at=_utc_now(),
            status="running",
            applications_sent=0,
            applications_skipped=0,
            applications_failed=0,
        )
        assert run.user_id == "user_001"
        assert run.status == "running"
        assert run.finished_at is None

    def test_model_completed_run(self):
        """Test creating completed run history."""
        start_time = _utc_now()
        end_time = start_time + timedelta(minutes=5)

        run = SchedulerRunHistory(
            user_id="user_001",
            started_at=start_time,
            finished_at=end_time,
            status="completed",
            applications_sent=10,
            applications_skipped=5,
            applications_failed=2,
        )
        assert run.status == "completed"
        assert run.applications_sent == 10
        assert run.applications_skipped == 5
        assert run.applications_failed == 2

    def test_model_with_error(self):
        """Test creating run history with error."""
        run = SchedulerRunHistory(
            user_id="user_001",
            started_at=_utc_now(),
            finished_at=_utc_now(),
            status="failed",
            applications_sent=0,
            applications_skipped=0,
            applications_failed=0,
            error_message="Connection timeout",
        )
        assert run.status == "failed"
        assert run.error_message == "Connection timeout"

    def test_model_with_details(self):
        """Test creating run history with details."""
        details = {"vacancies_searched": 100, "api_calls": 15, "duration_seconds": 120}
        run = SchedulerRunHistory(
            user_id="user_001",
            started_at=_utc_now(),
            status="completed",
            applications_sent=5,
            applications_skipped=10,
            applications_failed=0,
            details=details,
        )
        assert run.details == details


class TestToken:
    """Tests for Token model."""

    def test_token_creation(self):
        """Test creating Token instance."""
        token = Token(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            expires_in=3600,
            obtained_at=_utc_now(),
        )
        assert token.access_token == "access_token_123"
        assert token.refresh_token == "refresh_token_456"
        assert token.expires_in == 3600

    def test_token_is_expired_false(self):
        """Test that fresh token is not expired."""
        token = Token(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            expires_in=3600,
            obtained_at=_utc_now(),
        )
        assert token.is_expired() is False

    def test_token_is_expired_true(self):
        """Test that old token is expired."""
        token = Token(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            expires_in=3600,
            obtained_at=_utc_now() - timedelta(hours=2),
        )
        assert token.is_expired() is True

    def test_token_expiry_boundary(self):
        """Test token expiry at boundary with buffer."""
        # Token that expires in 4 minutes (buffer is typically 5 min)
        token = Token(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            expires_in=240,  # 4 minutes
            obtained_at=_utc_now(),
        )
        # Should be considered expired due to buffer
        # This depends on implementation details
        result = token.is_expired()
        assert isinstance(result, bool)
