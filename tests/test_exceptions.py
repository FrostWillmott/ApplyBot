"""Tests for custom exceptions."""

from fastapi import status

from app.core.exceptions import (
    APIError,
    ApplicationError,
    AuthenticationError,
    DuplicateApplicationError,
    FilteredVacancyError,
    forbidden_exception,
    not_found_exception,
    unauthorized_exception,
)


class TestApplicationError:
    """Tests for ApplicationError base exception."""

    def test_create_error(self):
        """Test creating ApplicationError."""
        error = ApplicationError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_inheritance(self):
        """Test that ApplicationError inherits from Exception."""
        error = ApplicationError("Test")
        assert isinstance(error, Exception)


class TestDuplicateApplicationError:
    """Tests for DuplicateApplicationError."""

    def test_create_error(self):
        """Test creating DuplicateApplicationError."""
        error = DuplicateApplicationError(vacancy_id="12345", resume_id="resume_123")
        assert error.vacancy_id == "12345"
        assert error.resume_id == "resume_123"
        assert "12345" in error.message
        assert "resume_123" in error.message

    def test_message_format(self):
        """Test error message format."""
        error = DuplicateApplicationError(vacancy_id="vac_001", resume_id="res_001")
        assert "Already applied" in error.message

    def test_inheritance(self):
        """Test inheritance from ApplicationError."""
        error = DuplicateApplicationError("123", "456")
        assert isinstance(error, ApplicationError)


class TestFilteredVacancyError:
    """Tests for FilteredVacancyError."""

    def test_create_error(self):
        """Test creating FilteredVacancyError."""
        error = FilteredVacancyError(vacancy_id="12345", reason="Company excluded")
        assert error.vacancy_id == "12345"
        assert error.reason == "Company excluded"

    def test_message_format(self):
        """Test error message format."""
        error = FilteredVacancyError(vacancy_id="vac_001", reason="Salary too low")
        assert "vac_001" in error.message
        assert "filtered out" in error.message.lower()
        assert "Salary too low" in error.message

    def test_inheritance(self):
        """Test inheritance from ApplicationError."""
        error = FilteredVacancyError("123", "reason")
        assert isinstance(error, ApplicationError)


class TestAPIError:
    """Tests for APIError."""

    def test_create_error(self):
        """Test creating APIError."""
        error = APIError(service="HH.ru", status_code=500, detail="Server error")
        assert error.service == "HH.ru"
        assert error.status_code == 500
        assert error.detail == "Server error"

    def test_message_format(self):
        """Test error message format."""
        error = APIError(service="API", status_code=404, detail="Not found")
        assert "API" in error.message
        assert "404" in error.message
        assert "Not found" in error.message

    def test_inheritance(self):
        """Test inheritance from ApplicationError."""
        error = APIError("service", 500, "detail")
        assert isinstance(error, ApplicationError)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_create_error_default_message(self):
        """Test creating AuthenticationError with default message."""
        error = AuthenticationError()
        assert error.detail == "Authentication failed"
        assert "Authentication failed" in str(error)

    def test_create_error_custom_message(self):
        """Test creating AuthenticationError with custom message."""
        error = AuthenticationError("Token expired")
        assert error.detail == "Token expired"
        assert "Token expired" in str(error)

    def test_inheritance(self):
        """Test inheritance from ApplicationError."""
        error = AuthenticationError()
        assert isinstance(error, ApplicationError)


class TestHTTPExceptionFactories:
    """Tests for HTTP exception factory functions."""

    def test_unauthorized_exception_default(self):
        """Test unauthorized exception with default message."""
        exc = unauthorized_exception()
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.detail == "Not authenticated"
        assert exc.headers == {"WWW-Authenticate": "Bearer"}

    def test_unauthorized_exception_custom_message(self):
        """Test unauthorized exception with custom message."""
        exc = unauthorized_exception("Token invalid")
        assert exc.detail == "Token invalid"

    def test_forbidden_exception_default(self):
        """Test forbidden exception with default message."""
        exc = forbidden_exception()
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == "Not enough permissions"

    def test_forbidden_exception_custom_message(self):
        """Test forbidden exception with custom message."""
        exc = forbidden_exception("Access denied")
        assert exc.detail == "Access denied"

    def test_not_found_exception_default(self):
        """Test not found exception with default message."""
        exc = not_found_exception()
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.detail == "Resource not found"

    def test_not_found_exception_custom_message(self):
        """Test not found exception with custom message."""
        exc = not_found_exception("Vacancy not found")
        assert exc.detail == "Vacancy not found"
