from typing import Any

from pydantic import BaseModel, Field


class ApplyRequest(BaseModel):
    """Base request for job applications."""

    position: str | None = Field(None, description="Target position or job title (optional, will be taken from resume if not provided)")
    resume: str | None = Field(None, description="Resume summary or content (optional, will be taken from resume if not provided)")
    skills: str | None = Field(None, description="Relevant skills (optional, will be taken from resume if not provided)")
    experience: str | None = Field(None, description="Work experience summary (optional, will be taken from resume if not provided)")
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
    experience_level: str | None = Field(
        default=None, description="Required experience level (e.g., 'noExperience', 'between1And3', 'between3And6', 'moreThan6')"
    )
    required_skills: list[str] | None = Field(
        default=None, description="List of required skills that must be present in the vacancy"
    )
    excluded_keywords: list[str] | None = Field(
        default=None, description="Keywords to exclude from job descriptions"
    )
    employment_types: list[str] | None = Field(
        default=None, description="Acceptable employment types (e.g., 'full', 'part', 'project')"
    )
    max_commute_time: int | None = Field(
        default=None, description="Maximum commute time in minutes"
    )
    preferred_schedule: list[str] | None = Field(
        default=None, description="Preferred work schedules (e.g., 'flexible', 'remote', 'shift')"
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
