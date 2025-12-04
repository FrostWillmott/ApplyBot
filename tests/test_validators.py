"""Tests for validation logic."""

import pytest

from app.schemas.apply import ApplyRequest
from app.utils.validators import (
    ValidationResult,
    validate_application_request,
    validate_bulk_application_limits,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result_creation(self):
        """Test creating a valid result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.error is None
        assert result.warnings == []

    def test_invalid_result_with_error(self):
        """Test creating an invalid result with error."""
        result = ValidationResult(is_valid=False, error="Test error")
        assert result.is_valid is False
        assert result.error == "Test error"

    def test_result_with_warnings(self):
        """Test creating result with warnings."""
        result = ValidationResult(is_valid=True, warnings=["Warning 1", "Warning 2"])
        assert result.is_valid is True
        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings

    def test_default_warnings_initialization(self):
        """Test that warnings default to empty list."""
        result = ValidationResult(is_valid=True)
        assert result.warnings is not None
        assert isinstance(result.warnings, list)


class TestValidateApplicationRequest:
    """Tests for validate_application_request function."""

    @pytest.mark.asyncio
    async def test_valid_request_passes(self, sample_apply_request):
        """Test that valid request passes validation."""
        result = await validate_application_request(sample_apply_request)
        assert result.is_valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_missing_resume_id_fails(self):
        """Test that missing resume_id fails validation."""
        request = ApplyRequest(
            position="Developer",
            resume="Good resume content here with enough characters",
            skills="Python, Django, FastAPI",
            experience="5 years of development experience",
            resume_id="",
        )
        result = await validate_application_request(request)
        assert result.is_valid is False
        assert "resume id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_whitespace_resume_id_fails(self):
        """Test that whitespace-only resume_id fails validation."""
        request = ApplyRequest(
            position="Developer",
            resume="Good resume content here",
            skills="Python, Django",
            experience="5 years experience",
            resume_id="   ",
        )
        result = await validate_application_request(request)
        assert result.is_valid is False
        assert "resume id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_short_resume_generates_warning(self):
        """Test that short resume generates warning."""
        request = ApplyRequest(
            position="Developer",
            resume="Short",
            skills="Python, Django, FastAPI, PostgreSQL",
            experience="5 years of software development experience",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is True
        assert any("short" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_short_skills_generates_warning(self):
        """Test that short skills description generates warning."""
        request = ApplyRequest(
            position="Developer",
            resume="Full resume content with enough characters to pass validation",
            skills="Py",
            experience="5 years of software development experience",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is True
        assert any("brief" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_short_experience_generates_warning(self):
        """Test that short experience description generates warning."""
        request = ApplyRequest(
            position="Developer",
            resume="Full resume content with enough characters to pass validation",
            skills="Python, Django, FastAPI, PostgreSQL",
            experience="5y",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is True
        assert any("short" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_template_content_lorem_ipsum_fails(self):
        """Test that lorem ipsum template content fails."""
        request = ApplyRequest(
            position="Developer",
            resume="Lorem ipsum dolor sit amet",
            skills="Python, Django",
            experience="5 years experience",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is False
        assert "template" in result.error.lower()

    @pytest.mark.asyncio
    async def test_template_content_sample_text_fails(self):
        """Test that sample text template content fails."""
        request = ApplyRequest(
            position="Developer",
            resume="This is sample text for testing",
            skills="Python, Django",
            experience="5 years experience",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is False
        assert "template" in result.error.lower()

    @pytest.mark.asyncio
    async def test_template_keyword_in_skills_fails(self):
        """Test that template keyword in skills fails."""
        request = ApplyRequest(
            position="Developer",
            resume="Good resume content",
            skills="template skills here",
            experience="5 years experience",
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is False
        assert "template" in result.error.lower()

    @pytest.mark.asyncio
    async def test_none_values_handled(self):
        """Test that None values are handled gracefully."""
        request = ApplyRequest(
            position=None,
            resume=None,
            skills=None,
            experience=None,
            resume_id="resume_123",
        )
        result = await validate_application_request(request)
        assert result.is_valid is True


class TestValidateBulkApplicationLimits:
    """Tests for validate_bulk_application_limits function."""

    def test_valid_limit_passes(self):
        """Test that valid application limit passes."""
        result = validate_bulk_application_limits(20)
        assert result.is_valid is True
        assert result.error is None

    def test_exceeding_daily_limit_fails(self):
        """Test that exceeding daily limit fails."""
        result = validate_bulk_application_limits(150, user_daily_limit=100)
        assert result.is_valid is False
        assert "daily limit" in result.error.lower()

    def test_high_count_generates_warning(self):
        """Test that high application count generates warning."""
        result = validate_bulk_application_limits(75)
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "rate limits" in result.warnings[0].lower()

    def test_exactly_at_api_safety_limit(self):
        """Test application count at API safety limit boundary."""
        result = validate_bulk_application_limits(50)
        assert result.is_valid is True
        assert len(result.warnings) == 0

    def test_just_above_api_safety_limit(self):
        """Test application count just above API safety limit."""
        result = validate_bulk_application_limits(51)
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_custom_daily_limit(self):
        """Test with custom daily limit."""
        result = validate_bulk_application_limits(200, user_daily_limit=250)
        assert result.is_valid is True

    def test_low_count_no_warnings(self):
        """Test that low application count has no warnings."""
        result = validate_bulk_application_limits(10)
        assert result.is_valid is True
        assert len(result.warnings) == 0
