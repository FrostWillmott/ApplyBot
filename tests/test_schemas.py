"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.apply import (
    ApplyRequest,
    ApplyResponse,
    BulkApplyRequest,
    CoverLetterRequest,
)
from app.schemas.scheduler import (
    ManualRunRequest,
    ManualRunResponse,
    RunHistoryItem,
    ScheduleConfig,
    SchedulerSettingsRequest,
    SearchCriteria,
)


class TestApplyRequest:
    """Tests for ApplyRequest schema."""

    def test_valid_request_creation(self):
        """Test creating valid ApplyRequest."""
        request = ApplyRequest(
            position="Developer",
            resume="Resume content",
            skills="Python, Django",
            experience="5 years",
            resume_id="resume_123",
        )
        assert request.position == "Developer"
        assert request.resume_id == "resume_123"

    def test_resume_id_required(self):
        """Test that resume_id is required."""
        with pytest.raises(ValidationError):
            ApplyRequest(position="Developer", resume="Content")

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        request = ApplyRequest(resume_id="123")
        assert request.position is None
        assert request.resume is None
        assert request.skills is None
        assert request.experience is None


class TestBulkApplyRequest:
    """Tests for BulkApplyRequest schema."""

    def test_valid_bulk_request(self):
        """Test creating valid BulkApplyRequest."""
        request = BulkApplyRequest(
            position="Python Developer",
            resume_id="123",
            exclude_companies=["Company A"],
            salary_min=100000,
            remote_only=True,
            required_skills=["Python", "Django"],
        )
        assert request.position == "Python Developer"
        assert request.exclude_companies == ["Company A"]
        assert request.salary_min == 100000
        assert request.remote_only is True

    def test_default_values(self):
        """Test default values for BulkApplyRequest."""
        request = BulkApplyRequest(resume_id="123")
        assert request.exclude_companies is None
        assert request.salary_min is None
        assert request.remote_only is False
        assert request.use_cover_letter is True

    def test_experience_level_values(self):
        """Test experience level field."""
        request = BulkApplyRequest(resume_id="123", experience_level="between1And3")
        assert request.experience_level == "between1And3"

    def test_employment_types_list(self):
        """Test employment types as list."""
        request = BulkApplyRequest(resume_id="123", employment_types=["full", "part"])
        assert request.employment_types == ["full", "part"]


class TestApplyResponse:
    """Tests for ApplyResponse schema."""

    def test_success_response(self):
        """Test creating success response."""
        response = ApplyResponse(
            vacancy_id="123",
            status="success",
            vacancy_title="Python Developer",
            cover_letter="Cover letter content",
        )
        assert response.vacancy_id == "123"
        assert response.status == "success"

    def test_error_response(self):
        """Test creating error response."""
        response = ApplyResponse(
            vacancy_id="123", status="error", error_detail="Application failed"
        )
        assert response.status == "error"
        assert response.error_detail == "Application failed"

    def test_skipped_response(self):
        """Test creating skipped response."""
        response = ApplyResponse(
            vacancy_id="123", status="skipped", error_detail="Already applied"
        )
        assert response.status == "skipped"


class TestCoverLetterRequest:
    """Tests for CoverLetterRequest schema."""

    def test_valid_request(self):
        """Test creating valid cover letter request."""
        request = CoverLetterRequest(
            job_title="Developer",
            company="Tech Corp",
            skills="Python",
            experience="5 years",
        )
        assert request.job_title == "Developer"
        assert request.company == "Tech Corp"

    def test_all_fields_required(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            CoverLetterRequest(job_title="Developer", company="Tech Corp")


class TestScheduleConfig:
    """Tests for ScheduleConfig schema."""

    def test_default_values(self):
        """Test default schedule configuration."""
        config = ScheduleConfig()
        assert config.hour == 9
        assert config.minute == 0
        assert config.days == "mon,tue,wed,thu,fri"
        assert config.timezone == "Europe/Moscow"

    def test_custom_values(self):
        """Test custom schedule configuration."""
        config = ScheduleConfig(hour=14, minute=30, days="mon,wed,fri", timezone="UTC")
        assert config.hour == 14
        assert config.minute == 30
        assert config.days == "mon,wed,fri"

    def test_hour_validation_min(self):
        """Test hour minimum validation."""
        config = ScheduleConfig(hour=0)
        assert config.hour == 0

    def test_hour_validation_max(self):
        """Test hour maximum validation."""
        config = ScheduleConfig(hour=23)
        assert config.hour == 23

    def test_hour_validation_invalid(self):
        """Test hour validation with invalid value."""
        with pytest.raises(ValidationError):
            ScheduleConfig(hour=24)

    def test_minute_validation(self):
        """Test minute validation."""
        with pytest.raises(ValidationError):
            ScheduleConfig(minute=60)


class TestSearchCriteria:
    """Tests for SearchCriteria schema."""

    def test_required_fields(self):
        """Test required fields for search criteria."""
        criteria = SearchCriteria(position="Python Developer", resume_id="123")
        assert criteria.position == "Python Developer"
        assert criteria.resume_id == "123"

    def test_missing_required_fields(self):
        """Test missing required fields."""
        with pytest.raises(ValidationError):
            SearchCriteria(position="Developer")

    def test_optional_fields(self):
        """Test optional fields."""
        criteria = SearchCriteria(
            position="Developer",
            resume_id="123",
            skills="Python",
            salary_min=100000,
            remote_only=True,
        )
        assert criteria.skills == "Python"
        assert criteria.salary_min == 100000
        assert criteria.remote_only is True


class TestSchedulerSettingsRequest:
    """Tests for SchedulerSettingsRequest schema."""

    def test_default_values(self):
        """Test default scheduler settings."""
        settings = SchedulerSettingsRequest()
        assert settings.enabled is False
        assert settings.max_applications_per_run == 10

    def test_max_applications_validation(self):
        """Test max applications validation."""
        settings = SchedulerSettingsRequest(max_applications_per_run=50)
        assert settings.max_applications_per_run == 50

    def test_max_applications_exceeds_limit(self):
        """Test max applications exceeds limit."""
        with pytest.raises(ValidationError):
            SchedulerSettingsRequest(max_applications_per_run=51)

    def test_min_applications(self):
        """Test minimum applications validation."""
        with pytest.raises(ValidationError):
            SchedulerSettingsRequest(max_applications_per_run=0)


class TestManualRunRequest:
    """Tests for ManualRunRequest schema."""

    def test_default_max_applications(self):
        """Test default max applications."""
        request = ManualRunRequest()
        assert request.max_applications == 10

    def test_custom_max_applications(self):
        """Test custom max applications."""
        request = ManualRunRequest(max_applications=25)
        assert request.max_applications == 25

    def test_validation_bounds(self):
        """Test validation bounds."""
        with pytest.raises(ValidationError):
            ManualRunRequest(max_applications=0)
        with pytest.raises(ValidationError):
            ManualRunRequest(max_applications=51)


class TestManualRunResponse:
    """Tests for ManualRunResponse schema."""

    def test_success_response(self):
        """Test successful manual run response."""
        response = ManualRunResponse(
            status="completed",
            message="Run completed successfully",
            run_id=1,
            applications_sent=5,
        )
        assert response.status == "completed"
        assert response.applications_sent == 5

    def test_default_values(self):
        """Test default values."""
        response = ManualRunResponse(status="started", message="Run started")
        assert response.run_id is None
        assert response.applications_sent == 0
        assert response.results is None


class TestRunHistoryItem:
    """Tests for RunHistoryItem schema."""

    def test_valid_history_item(self):
        """Test creating valid run history item."""
        from datetime import datetime

        item = RunHistoryItem(
            id=1,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status="completed",
            applications_sent=10,
            applications_skipped=5,
            applications_failed=2,
            error_message=None,
        )
        assert item.id == 1
        assert item.status == "completed"
        assert item.applications_sent == 10
