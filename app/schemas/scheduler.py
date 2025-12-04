"""Schemas for scheduler API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduleConfig(BaseModel):
    """Schedule configuration."""

    hour: int = Field(default=9, ge=0, le=23, description="Hour to run (0-23)")
    minute: int = Field(default=0, ge=0, le=59, description="Minute to run (0-59)")
    days: str = Field(
        default="mon,tue,wed,thu,fri",
        description="Days to run (comma-separated)",
    )
    timezone: str = Field(default="Europe/Moscow", description="Timezone")


class SearchCriteria(BaseModel):
    """Search criteria for auto-apply."""

    position: str = Field(..., description="Target position to search")
    resume_id: str = Field(..., description="Resume ID for applications")
    skills: str | None = Field(default=None, description="Skills for cover letter")
    experience: str | None = Field(default=None, description="Experience summary")
    exclude_companies: list[str] | None = Field(
        default=None, description="Companies to exclude"
    )
    salary_min: int | None = Field(default=None, description="Minimum salary")
    remote_only: bool = Field(default=False, description="Only remote positions")
    experience_level: str | None = Field(
        default=None, description="Experience level filter"
    )
    use_cover_letter: bool = Field(
        default=True, description="Generate AI cover letters"
    )


class SchedulerSettingsRequest(BaseModel):
    """Request to update scheduler settings."""

    enabled: bool = Field(default=False, description="Enable/disable scheduler")
    schedule: ScheduleConfig | None = Field(default=None, description="Schedule config")
    max_applications_per_run: int = Field(
        default=10, ge=1, le=50, description="Max applications per run"
    )
    search_criteria: SearchCriteria | None = Field(
        default=None, description="Search criteria"
    )


class SchedulerSettingsResponse(BaseModel):
    """Response with current scheduler settings."""

    user_id: str
    enabled: bool
    schedule: ScheduleConfig
    max_applications_per_run: int
    search_criteria: SearchCriteria | None

    last_run_at: datetime | None
    last_run_status: str | None
    last_run_applications: int
    total_applications: int

    next_run_at: datetime | None

    created_at: datetime
    updated_at: datetime


class SchedulerStatusResponse(BaseModel):
    """Response with scheduler status."""

    scheduler_running: bool
    jobs_count: int
    next_scheduled_run: datetime | None
    user_settings: SchedulerSettingsResponse | None


class RunHistoryItem(BaseModel):
    """Single run history entry."""

    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    applications_sent: int
    applications_skipped: int
    applications_failed: int
    error_message: str | None


class RunHistoryResponse(BaseModel):
    """Response with run history."""

    runs: list[RunHistoryItem]
    total_count: int


class ManualRunRequest(BaseModel):
    """Request to trigger a manual run."""

    max_applications: int = Field(
        default=10, ge=1, le=50, description="Max applications for this run"
    )


class ManualRunResponse(BaseModel):
    """Response from manual run trigger."""

    status: str
    message: str
    run_id: int | None = None
    applications_sent: int = 0
    results: list[dict[str, Any]] | None = None
