"""Custom exceptions for the application."""

from fastapi import HTTPException, status


class ApplicationError(Exception):
    """Base exception for application errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class DuplicateApplicationError(ApplicationError):
    """Raised when attempting to apply to a vacancy that has already been applied to."""
    def __init__(self, vacancy_id: str, resume_id: str):
        self.vacancy_id = vacancy_id
        self.resume_id = resume_id
        message = f"Already applied to vacancy {vacancy_id} with resume {resume_id}"
        super().__init__(message)


class FilteredVacancyError(ApplicationError):
    """Raised when a vacancy is filtered out by application criteria."""
    def __init__(self, vacancy_id: str, reason: str):
        self.vacancy_id = vacancy_id
        self.reason = reason
        message = f"Vacancy {vacancy_id} filtered out: {reason}"
        super().__init__(message)


class APIError(ApplicationError):
    """Raised when an API request fails."""
    def __init__(self, service: str, status_code: int, detail: str):
        self.service = service
        self.status_code = status_code
        self.detail = detail
        message = f"{service} API error ({status_code}): {detail}"
        super().__init__(message)


class AuthenticationError(ApplicationError):
    """Raised when authentication fails."""
    def __init__(self, detail: str = "Authentication failed"):
        self.detail = detail
        super().__init__(detail)


# HTTP Exception factory functions
def unauthorized_exception(detail: str = "Not authenticated"):
    """Return a 401 Unauthorized exception."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_exception(detail: str = "Not enough permissions"):
    """Return a 403 Forbidden exception."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def not_found_exception(detail: str = "Resource not found"):
    """Return a 404 Not Found exception."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )