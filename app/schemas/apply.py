from typing import Any

from pydantic import BaseModel, Field


class ApplyRequest(BaseModel):
    """Base request for job applications."""

    position: str = Field(..., description="Target position or job title")
    resume: str = Field(..., description="Resume summary or content")
    skills: str = Field(..., description="Relevant skills")
    experience: str = Field(..., description="Work experience summary")
    resume_id: str = Field(..., description="HH.ru resume ID for applications")


class BulkApplyRequest(ApplyRequest):
    """Request for bulk applications with additional search criteria."""

    exclude_companies: list[str] | None = Field(
        default=None, description="Company names to exclude from applications"
    )
    salary_min: int | None = Field(
        default=None, description="Minimum salary requirement"
    )
    remote_only: bool | None = Field(
        default=False, description="Only apply to remote positions"
    )


class ApplyResponse(BaseModel):
    """Response for application attempts."""

    vacancy_id: str
    status: str = Field(..., description="success, error, or skipped")
    vacancy_title: str | None = None
    cover_letter: str | None = None
    hh_response: dict[str, Any] | None = None
    error_detail: str | None = None


class CoverLetterRequest(BaseModel):
    """Legacy schema for cover letter generation only."""

    job_title: str
    company: str
    skills: str
    experience: str
