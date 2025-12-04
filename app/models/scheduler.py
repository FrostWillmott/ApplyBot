"""Scheduler models for auto-apply functionality."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.storage import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SchedulerSettings(Base):
    """Model for storing scheduler configuration per user."""

    __tablename__ = "scheduler_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    schedule_hour: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    schedule_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    schedule_days: Mapped[str] = mapped_column(
        String(50), default="mon,tue,wed,thu,fri", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(50), default="Europe/Moscow", nullable=False
    )

    max_applications_per_run: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    resume_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    search_criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_run_applications: Mapped[int] = mapped_column(Integer, default=0)
    total_applications: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now, onupdate=_utc_now, nullable=False
    )


class SchedulerRunHistory(Base):
    """Model for tracking scheduler run history."""

    __tablename__ = "scheduler_run_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    applications_sent: Mapped[int] = mapped_column(Integer, default=0)
    applications_skipped: Mapped[int] = mapped_column(Integer, default=0)
    applications_failed: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
