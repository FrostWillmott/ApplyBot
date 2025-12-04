"""Schemas for job application requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


class ApplyRequest(BaseModel):
    """Base request for job applications."""

    position: str | None = Field(None, description="Target position or job title")
    resume: str | None = Field(None, description="Resume summary or content")
    skills: str | None = Field(None, description="Relevant skills")
    experience: str | None = Field(None, description="Work experience summary")
    resume_id: str = Field(..., description="HH.ru resume ID for applications")


class BulkApplyRequest(ApplyRequest):
    """Request for bulk applications with search criteria."""

    exclude_companies: list[str] | None = Field(
        default=None, description="Company names to exclude"
    )
    salary_min: int | None = Field(default=None, description="Minimum salary")
    remote_only: bool = Field(default=False, description="Only remote positions")
    experience_level: str | None = Field(
        default=None,
        description="Experience level (noExperience, between1And3, between3And6, moreThan6)",
    )
    required_skills: list[str] | None = Field(
        default=None, description="Required skills in vacancy"
    )
    excluded_keywords: list[str] | None = Field(
        default=None, description="Keywords to exclude"
    )
    employment_types: list[str] | None = Field(
        default=None, description="Employment types (full, part, project)"
    )
    max_commute_time: int | None = Field(
        default=None, description="Max commute time in minutes"
    )
    preferred_schedule: list[str] | None = Field(
        default=None, description="Preferred schedules (flexible, remote, shift)"
    )
    use_cover_letter: bool = Field(
        default=True, description="Generate AI cover letters"
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
    """Legacy schema for cover letter generation."""

    job_title: str
    company: str
    skills: str
    experience: str
