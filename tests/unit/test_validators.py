"""Unit tests for validation logic."""

import pytest

from app.schemas.apply import ApplyRequest, BulkApplyRequest
from app.utils.validators import (
    validate_application_request,
    validate_bulk_application_limits,
)


class TestApplicationValidators:
    """Test application validation logic."""

    @pytest.mark.asyncio
    async def test_valid_application_request(self, sample_apply_request):
        """Test validation of valid application request."""
        result = await validate_application_request(sample_apply_request)
        assert result.is_valid
        assert result.error is None

    @pytest.mark.asyncio
    async def test_empty_resume_id_validation(self):
        """Test validation fails for empty resume ID."""
        request = ApplyRequest(
            position="Developer",
            resume="Good resume",
            skills="Python",
            experience="5 years",
            resume_id="",
        )
        result = await validate_application_request(request)
        assert not result.is_valid
        assert "Resume ID is required" in result.error

    @pytest.mark.asyncio
    async def test_template_content_detection(self):
        """Test template content detection."""
        request = ApplyRequest(
            position="Developer",
            resume="Lorem ipsum dolor sit amet",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert not result.is_valid
        assert "Template content detected" in result.error

    @pytest.mark.asyncio
    async def test_short_content_warnings(self):
        """Test warnings for short content."""
        request = ApplyRequest(
            position="Developer",
            resume="Short",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid
        assert "Resume content is very short" in result.warnings

    def test_bulk_application_limits_valid(self):
        """Test valid bulk application limits."""
        result = validate_bulk_application_limits(20)
        assert result.is_valid
        assert not result.warnings

    def test_bulk_application_limits_exceeded(self):
        """Test bulk application limits exceeded."""
        result = validate_bulk_application_limits(150, user_daily_limit=100)
        assert not result.is_valid
        assert "Cannot exceed daily limit" in result.error

    def test_bulk_application_limits_warning(self):
        """Test warning for high application count."""
        result = validate_bulk_application_limits(60)
        assert result.is_valid
        assert "High application count" in result.warnings[0]