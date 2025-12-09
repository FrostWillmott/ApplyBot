"""API routes for scheduler management."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.scheduler import (
    ManualRunRequest,
    ManualRunResponse,
    RunHistoryItem,
    RunHistoryResponse,
    SchedulerSettingsRequest,
    SchedulerSettingsResponse,
    SchedulerStatusResponse,
)
from app.services.scheduler_service import (
    SchedulerService,
    get_scheduler_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


DEFAULT_USER_ID = "single_user"  # Single-user mode for personal use


def _get_current_user_id() -> str:
    """Get current user ID from session/token.

    Note: Single-user mode for personal deployment.
    """
    return DEFAULT_USER_ID


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Get the current scheduler status."""
    try:
        status = scheduler.get_status()
        user_id = _get_current_user_id()
        user_settings = await scheduler.get_user_settings(user_id)

        return SchedulerStatusResponse(
            scheduler_running=status["scheduler_running"],
            jobs_count=status["jobs_count"],
            next_scheduled_run=status.get("next_scheduled_run"),
            user_settings=user_settings,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except ValueError as e:
        logger.error(f"Invalid scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings", response_model=SchedulerSettingsResponse | None)
async def get_settings(
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Get current user's scheduler settings."""
    try:
        user_id = _get_current_user_id()
        settings_response = await scheduler.get_user_settings(user_id)
        return settings_response
    except SQLAlchemyError as e:
        logger.error(f"Database error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/settings", response_model=SchedulerSettingsResponse)
async def update_settings(
    request: SchedulerSettingsRequest,
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Update scheduler settings for the current user."""
    try:
        user_id = _get_current_user_id()
        result = await scheduler.update_user_settings(user_id, request)

        status = "enabled" if request.enabled else "disabled"
        logger.info(f"Scheduler settings updated for user {user_id}: {status}")

        return result
    except SQLAlchemyError as e:
        logger.error(f"Database error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except ValueError as e:
        logger.error(f"Invalid settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/enable")
async def enable_scheduler(
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Enable the scheduler for the current user."""
    try:
        user_id = _get_current_user_id()
        current_settings = await scheduler.get_user_settings(user_id)

        if not current_settings:
            raise HTTPException(
                status_code=400,
                detail="No scheduler settings found. Please configure settings first.",
            )

        if not current_settings.search_criteria:
            raise HTTPException(
                status_code=400,
                detail="No search criteria configured. Please configure settings first.",
            )

        # Create update request with enabled=True
        update_request = SchedulerSettingsRequest(
            enabled=True,
            schedule=current_settings.schedule,
            max_applications_per_run=current_settings.max_applications_per_run,
            search_criteria=current_settings.search_criteria,
        )

        await scheduler.update_user_settings(user_id, update_request)

        return {"status": "success", "message": "Scheduler enabled"}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error enabling scheduler: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/disable")
async def disable_scheduler(
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Disable the scheduler for the current user."""
    try:
        user_id = _get_current_user_id()
        current_settings = await scheduler.get_user_settings(user_id)

        if not current_settings:
            return {
                "status": "success",
                "message": "Scheduler was not configured",
            }

        # Create update request with enabled=False
        update_request = SchedulerSettingsRequest(
            enabled=False,
            schedule=current_settings.schedule,
            max_applications_per_run=current_settings.max_applications_per_run,
            search_criteria=current_settings.search_criteria,
        )

        await scheduler.update_user_settings(user_id, update_request)

        return {"status": "success", "message": "Scheduler disabled"}
    except SQLAlchemyError as e:
        logger.error(f"Database error disabling scheduler: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/run", response_model=ManualRunResponse)
async def trigger_manual_run(
    request: ManualRunRequest = ManualRunRequest(),
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Trigger a manual run of the auto-apply job."""
    try:
        user_id = _get_current_user_id()
        result = await scheduler.trigger_manual_run(user_id, request.max_applications)
        return result
    except httpx.RequestError as e:
        logger.error(f"Network error during manual run: {e}")
        raise HTTPException(status_code=502, detail="Network error")
    except SQLAlchemyError as e:
        logger.error(f"Database error during manual run: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except ValueError as e:
        logger.error(f"Invalid request for manual run: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop")
async def stop_running_job(
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Stop the currently running auto-apply job."""
    try:
        user_id = _get_current_user_id()
        cancelled = await scheduler.cancel_running_job(user_id)

        if cancelled:
            return {"status": "success", "message": "Cancellation requested"}
        else:
            return {"status": "info", "message": "No running job to cancel"}
    except SQLAlchemyError as e:
        logger.error(f"Database error stopping job: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/history", response_model=RunHistoryResponse)
async def get_run_history(
    limit: int = Query(default=20, le=100),
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    """Get the run history for the current user."""
    try:
        user_id = _get_current_user_id()
        runs = await scheduler.get_run_history(user_id, limit)

        history_items = [
            RunHistoryItem(
                id=run.id,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=run.status,
                applications_sent=run.applications_sent,
                applications_skipped=run.applications_skipped,
                applications_failed=run.applications_failed,
                error_message=run.error_message,
            )
            for run in runs
        ]

        return RunHistoryResponse(runs=history_items, total_count=len(history_items))
    except SQLAlchemyError as e:
        logger.error(f"Database error getting run history: {e}")
        raise HTTPException(status_code=500, detail="Database error")
