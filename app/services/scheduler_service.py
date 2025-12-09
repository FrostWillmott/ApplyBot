"""Scheduler service for automated job applications."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.storage import async_session
from app.models.scheduler import SchedulerRunHistory, SchedulerSettings
from app.schemas.apply import BulkApplyRequest
from app.schemas.scheduler import (
    ManualRunResponse,
    ScheduleConfig,
    SchedulerSettingsRequest,
    SchedulerSettingsResponse,
    SearchCriteria,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """Get current time as UTC naive datetime for DB storage."""
    return datetime.now(UTC).replace(tzinfo=None)


class SchedulerService:
    """Service for managing scheduled auto-apply jobs."""

    _instance: "SchedulerService | None" = None
    _scheduler: AsyncIOScheduler | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._scheduler = None
        self._running_jobs: dict[str, bool] = {}
        self._cancel_requested: dict[str, bool] = {}

    @property
    def scheduler(self) -> AsyncIOScheduler | None:
        return self._scheduler

    async def start(self):
        """Start the scheduler."""
        if self._scheduler is not None and self._scheduler.running:
            logger.info("Scheduler already running")
            return

        self._scheduler = AsyncIOScheduler(timezone=settings.scheduler_default_timezone)
        self._scheduler.start()
        logger.info("Scheduler started")

        if settings.scheduler_auto_start:
            await self._load_all_user_jobs()

    async def stop(self):
        """Stop the scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Scheduler stopped")

    async def _load_all_user_jobs(self):
        """Load and schedule all enabled user jobs."""
        async with async_session() as session:
            query = select(SchedulerSettings).where(SchedulerSettings.enabled)
            result = await session.execute(query)
            user_settings = result.scalars().all()

            for user_setting in user_settings:
                await self._schedule_user_job(user_setting)
                logger.info(f"Loaded scheduled job for user {user_setting.user_id}")

    async def _schedule_user_job(self, user_settings: SchedulerSettings):
        """Schedule a job for a specific user."""
        if self._scheduler is None:
            logger.warning("Scheduler not initialized")
            return

        job_id = f"auto_apply_{user_settings.user_id}"

        # Remove existing job if any
        existing_job = self._scheduler.get_job(job_id)
        if existing_job:
            self._scheduler.remove_job(job_id)

        if not user_settings.enabled:
            logger.info(f"Scheduler disabled for user {user_settings.user_id}")
            return

        # Parse days
        days_map = {
            "mon": "0",
            "tue": "1",
            "wed": "2",
            "thu": "3",
            "fri": "4",
            "sat": "5",
            "sun": "6",
        }
        days = user_settings.schedule_days.lower().split(",")
        cron_days = ",".join(
            days_map.get(d.strip(), "0") for d in days if d.strip() in days_map
        )

        if not cron_days:
            cron_days = "0,1,2,3,4"  # Default to weekdays

        trigger = CronTrigger(
            hour=user_settings.schedule_hour,
            minute=user_settings.schedule_minute,
            day_of_week=cron_days,
            timezone=user_settings.timezone,
        )

        self._scheduler.add_job(
            self._run_auto_apply,
            trigger=trigger,
            id=job_id,
            args=[user_settings.user_id],
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # Get next run time from the scheduled job for accurate logging
        job = self._scheduler.get_job(job_id)
        next_run = job.next_run_time if job else None
        logger.info(
            f"Scheduled auto-apply for user {user_settings.user_id} "
            f"at {user_settings.schedule_hour}:{user_settings.schedule_minute:02d} "
            f"on days {user_settings.schedule_days}, next run: {next_run}"
        )

    async def _run_auto_apply(self, user_id: str):
        """Execute auto-apply for a user."""
        if self._running_jobs.get(user_id):
            logger.warning(f"Auto-apply already running for user {user_id}, skipping")
            return

        self._running_jobs[user_id] = True
        run_history = None

        try:
            logger.info(f"Starting auto-apply for user {user_id}")

            async with async_session() as session:
                # Get user settings
                query = select(SchedulerSettings).where(
                    SchedulerSettings.user_id == user_id
                )
                result = await session.execute(query)
                user_settings = result.scalar_one_or_none()

                if not user_settings or not user_settings.enabled:
                    logger.info(f"Auto-apply disabled for user {user_id}")
                    return

                if not user_settings.search_criteria:
                    logger.warning(f"No search criteria configured for user {user_id}")
                    return

                # Create run history entry
                run_history = SchedulerRunHistory(
                    user_id=user_id, started_at=_now(), status="running"
                )
                session.add(run_history)
                await session.commit()
                await session.refresh(run_history)

            # Execute bulk apply
            results = await self._execute_bulk_apply(
                user_id=user_id,
                search_criteria=user_settings.search_criteria,
                max_applications=user_settings.max_applications_per_run,
                resume_id=user_settings.resume_id,
            )

            # Update statistics
            sent = sum(1 for r in results if r.get("status") == "success")
            skipped = sum(1 for r in results if r.get("status") == "skipped")
            failed = sum(1 for r in results if r.get("status") == "error")

            async with async_session() as session:
                # Update run history
                if run_history:
                    await session.execute(
                        update(SchedulerRunHistory)
                        .where(SchedulerRunHistory.id == run_history.id)
                        .values(
                            finished_at=_now(),
                            status="completed",
                            applications_sent=sent,
                            applications_skipped=skipped,
                            applications_failed=failed,
                            details={"results": results},
                        )
                    )

                # Update user settings statistics
                await session.execute(
                    update(SchedulerSettings)
                    .where(SchedulerSettings.user_id == user_id)
                    .values(
                        last_run_at=_now(),
                        last_run_status="completed",
                        last_run_applications=sent,
                        total_applications=SchedulerSettings.total_applications + sent,
                    )
                )
                await session.commit()

            logger.info(
                f"Auto-apply completed for user {user_id}: "
                f"sent={sent}, skipped={skipped}, failed={failed}"
            )

        except httpx.RequestError as e:
            logger.error(f"Auto-apply network error for user {user_id}: {e}")
            await self._record_run_failure(user_id, run_history, f"Network error: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Auto-apply database error for user {user_id}: {e}")
            # Don't try to update DB if we have a DB error
        except ValueError as e:
            logger.error(f"Auto-apply validation error for user {user_id}: {e}")
            await self._record_run_failure(user_id, run_history, str(e))

        finally:
            self._running_jobs[user_id] = False
            self._cancel_requested[user_id] = False

    async def _record_run_failure(
        self,
        user_id: str,
        run_history: SchedulerRunHistory | None,
        error_message: str,
    ) -> None:
        """Record failure in run history and settings."""
        try:
            async with async_session() as session:
                if run_history:
                    await session.execute(
                        update(SchedulerRunHistory)
                        .where(SchedulerRunHistory.id == run_history.id)
                        .values(
                            finished_at=_now(),
                            status="failed",
                            error_message=error_message,
                        )
                    )

                await session.execute(
                    update(SchedulerSettings)
                    .where(SchedulerSettings.user_id == user_id)
                    .values(last_run_at=_now(), last_run_status="failed")
                )
                await session.commit()
        except SQLAlchemyError as db_error:
            logger.error(f"Failed to record run failure: {db_error}")

    def is_cancel_requested(self, user_id: str) -> bool:
        """Check if cancellation was requested for user."""
        return self._cancel_requested.get(user_id, False)

    async def cancel_running_job(self, user_id: str) -> bool:
        """Request cancellation of running job for user."""
        if not self._running_jobs.get(user_id):
            return False
        self._cancel_requested[user_id] = True
        logger.info(f"Cancellation requested for user {user_id}")
        return True

    def is_job_running(self, user_id: str) -> bool:
        """Check if a job is running for user."""
        return self._running_jobs.get(user_id, False)

    async def _execute_bulk_apply(
        self,
        user_id: str,
        search_criteria: dict,
        max_applications: int,
        resume_id: str | None,
    ) -> list[dict[str, Any]]:
        """Execute bulk apply using the application service."""
        from app.services.application_service import ApplicationService
        from app.services.hh_client import HHClient
        from app.services.llm.factory import get_llm_provider

        # Create dependencies
        hh_client = HHClient()
        llm_provider = get_llm_provider()
        service = ApplicationService(hh_client, llm_provider)

        # Build request from search criteria
        request = BulkApplyRequest(
            position=search_criteria.get("position", ""),
            resume_id=resume_id or search_criteria.get("resume_id", ""),
            skills=search_criteria.get("skills"),
            experience=search_criteria.get("experience"),
            exclude_companies=search_criteria.get("exclude_companies"),
            salary_min=search_criteria.get("salary_min"),
            remote_only=search_criteria.get("remote_only", False),
            experience_level=search_criteria.get("experience_level"),
            use_cover_letter=search_criteria.get("use_cover_letter", True),
        )

        # Execute bulk apply with cancellation check
        results = await service.bulk_apply(
            request=request,
            max_applications=max_applications,
            user_id=user_id,
            cancel_check=lambda: self.is_cancel_requested(user_id),
        )

        return [
            {
                "vacancy_id": r.vacancy_id,
                "status": r.status,
                "vacancy_title": r.vacancy_title,
                "error_detail": r.error_detail,
            }
            for r in results
        ]

    async def get_user_settings(self, user_id: str) -> SchedulerSettingsResponse | None:
        """Get scheduler settings for a user."""
        async with async_session() as session:
            query = select(SchedulerSettings).where(
                SchedulerSettings.user_id == user_id
            )
            result = await session.execute(query)
            user_settings = result.scalar_one_or_none()

            if not user_settings:
                return None

            # Calculate next run time from CronTrigger for accuracy
            next_run_at = None
            if self._scheduler and user_settings.enabled:
                job = self._scheduler.get_job(f"auto_apply_{user_id}")
                if job and job.next_run_time:
                    # APScheduler returns timezone-aware datetime
                    # Convert to user's timezone for display
                    user_tz = ZoneInfo(user_settings.timezone)
                    next_run_at = job.next_run_time.astimezone(user_tz)
                    logger.debug(
                        f"Next run for {user_id}: {next_run_at} "
                        f"(raw: {job.next_run_time})"
                    )

            search_criteria = None
            if user_settings.search_criteria:
                search_criteria = SearchCriteria(**user_settings.search_criteria)

            return SchedulerSettingsResponse(
                user_id=user_settings.user_id,
                enabled=user_settings.enabled,
                schedule=ScheduleConfig(
                    hour=user_settings.schedule_hour,
                    minute=user_settings.schedule_minute,
                    days=user_settings.schedule_days,
                    timezone=user_settings.timezone,
                ),
                max_applications_per_run=user_settings.max_applications_per_run,
                search_criteria=search_criteria,
                last_run_at=user_settings.last_run_at,
                last_run_status=user_settings.last_run_status,
                last_run_applications=user_settings.last_run_applications,
                total_applications=user_settings.total_applications,
                next_run_at=next_run_at,
                created_at=user_settings.created_at,
                updated_at=user_settings.updated_at,
            )

    async def update_user_settings(
        self, user_id: str, request: SchedulerSettingsRequest
    ) -> SchedulerSettingsResponse:
        """Update scheduler settings for a user."""
        async with async_session() as session:
            query = select(SchedulerSettings).where(
                SchedulerSettings.user_id == user_id
            )
            result = await session.execute(query)
            user_settings = result.scalar_one_or_none()

            if not user_settings:
                # Create new settings
                user_settings = SchedulerSettings(
                    user_id=user_id,
                    enabled=request.enabled,
                    schedule_hour=request.schedule.hour
                    if request.schedule
                    else settings.scheduler_default_hour,
                    schedule_minute=request.schedule.minute
                    if request.schedule
                    else settings.scheduler_default_minute,
                    schedule_days=request.schedule.days
                    if request.schedule
                    else settings.scheduler_default_days,
                    timezone=request.schedule.timezone
                    if request.schedule
                    else settings.scheduler_default_timezone,
                    max_applications_per_run=request.max_applications_per_run,
                    search_criteria=request.search_criteria.model_dump()
                    if request.search_criteria
                    else None,
                    resume_id=request.search_criteria.resume_id
                    if request.search_criteria
                    else None,
                )
                session.add(user_settings)
            else:
                # Update existing settings
                user_settings.enabled = request.enabled
                if request.schedule:
                    user_settings.schedule_hour = request.schedule.hour
                    user_settings.schedule_minute = request.schedule.minute
                    user_settings.schedule_days = request.schedule.days
                    user_settings.timezone = request.schedule.timezone
                user_settings.max_applications_per_run = (
                    request.max_applications_per_run
                )
                if request.search_criteria:
                    user_settings.search_criteria = request.search_criteria.model_dump()
                    user_settings.resume_id = request.search_criteria.resume_id

            await session.commit()
            await session.refresh(user_settings)

            # Reschedule the job
            await self._schedule_user_job(user_settings)

            return await self.get_user_settings(user_id)

    async def trigger_manual_run(
        self, user_id: str, max_applications: int = 10
    ) -> ManualRunResponse:
        """Trigger a manual run of auto-apply."""
        async with async_session() as session:
            query = select(SchedulerSettings).where(
                SchedulerSettings.user_id == user_id
            )
            result = await session.execute(query)
            user_settings = result.scalar_one_or_none()

            if not user_settings:
                return ManualRunResponse(
                    status="error",
                    message="No scheduler settings found. Please configure settings first.",
                )

            if not user_settings.search_criteria:
                return ManualRunResponse(
                    status="error",
                    message="No search criteria configured. Please configure settings first.",
                )

        if self._running_jobs.get(user_id):
            return ManualRunResponse(
                status="error",
                message="Auto-apply is already running for this user.",
            )

        # Run in background
        asyncio.create_task(self._run_auto_apply(user_id))

        return ManualRunResponse(
            status="started",
            message=f"Manual auto-apply run started with max {max_applications} applications.",
        )

    async def get_run_history(
        self, user_id: str, limit: int = 20
    ) -> list[SchedulerRunHistory]:
        """Get run history for a user."""
        async with async_session() as session:
            query = (
                select(SchedulerRunHistory)
                .where(SchedulerRunHistory.user_id == user_id)
                .order_by(SchedulerRunHistory.started_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return result.scalars().all()

    def get_status(self) -> dict:
        """Get scheduler status."""
        if self._scheduler is None:
            return {"scheduler_running": False, "jobs_count": 0}

        jobs = self._scheduler.get_jobs()
        next_run = None
        if jobs:
            next_runs = [j.next_run_time for j in jobs if j.next_run_time]
            if next_runs:
                # APScheduler returns timezone-aware datetimes
                next_run = min(next_runs)
                # Convert to default timezone for consistent display
                default_tz = ZoneInfo(settings.scheduler_default_timezone)
                next_run = next_run.astimezone(default_tz)

        return {
            "scheduler_running": self._scheduler.running,
            "jobs_count": len(jobs),
            "next_scheduled_run": next_run,
        }


# Global scheduler service instance
scheduler_service = SchedulerService()


async def get_scheduler_service() -> SchedulerService:
    """Dependency to get scheduler service."""
    return scheduler_service
