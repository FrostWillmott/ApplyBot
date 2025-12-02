"""API routes for scheduler management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.scheduler import (
    ManualRunRequest,
    ManualRunResponse,
    RunHistoryItem,
    RunHistoryResponse,
    SchedulerSettingsRequest,
    SchedulerSettingsResponse,
    SchedulerStatusResponse,
)
from app.services.scheduler_service import SchedulerService, get_scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def _get_current_user_id() -> str:
    """Get current user ID from session/token.
    
    TODO: Implement proper user authentication.
    For now, returns a default user ID.
    """
    return "default_user"


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    scheduler: SchedulerService = Depends(get_scheduler_service)
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
            user_settings=user_settings
        )
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {e}")


@router.get("/settings", response_model=SchedulerSettingsResponse | None)
async def get_settings(
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Get current user's scheduler settings."""
    try:
        user_id = _get_current_user_id()
        settings_response = await scheduler.get_user_settings(user_id)
        return settings_response
    except Exception as e:
        logger.error(f"Failed to get scheduler settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler settings: {e}")


@router.post("/settings", response_model=SchedulerSettingsResponse)
async def update_settings(
    request: SchedulerSettingsRequest,
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Update scheduler settings for the current user."""
    try:
        user_id = _get_current_user_id()
        result = await scheduler.update_user_settings(user_id, request)
        
        status = "enabled" if request.enabled else "disabled"
        logger.info(f"Scheduler settings updated for user {user_id}: {status}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to update scheduler settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update scheduler settings: {e}")


@router.post("/enable")
async def enable_scheduler(
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Enable the scheduler for the current user."""
    try:
        user_id = _get_current_user_id()
        current_settings = await scheduler.get_user_settings(user_id)
        
        if not current_settings:
            raise HTTPException(
                status_code=400, 
                detail="No scheduler settings found. Please configure settings first."
            )
        
        if not current_settings.search_criteria:
            raise HTTPException(
                status_code=400,
                detail="No search criteria configured. Please configure settings first."
            )
        
        # Create update request with enabled=True
        update_request = SchedulerSettingsRequest(
            enabled=True,
            schedule=current_settings.schedule,
            max_applications_per_run=current_settings.max_applications_per_run,
            search_criteria=current_settings.search_criteria
        )
        
        await scheduler.update_user_settings(user_id, update_request)
        
        return {"status": "success", "message": "Scheduler enabled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable scheduler: {e}")


@router.post("/disable")
async def disable_scheduler(
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Disable the scheduler for the current user."""
    try:
        user_id = _get_current_user_id()
        current_settings = await scheduler.get_user_settings(user_id)
        
        if not current_settings:
            return {"status": "success", "message": "Scheduler was not configured"}
        
        # Create update request with enabled=False
        update_request = SchedulerSettingsRequest(
            enabled=False,
            schedule=current_settings.schedule,
            max_applications_per_run=current_settings.max_applications_per_run,
            search_criteria=current_settings.search_criteria
        )
        
        await scheduler.update_user_settings(user_id, update_request)
        
        return {"status": "success", "message": "Scheduler disabled"}
    except Exception as e:
        logger.error(f"Failed to disable scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable scheduler: {e}")


@router.post("/run", response_model=ManualRunResponse)
async def trigger_manual_run(
    request: ManualRunRequest = ManualRunRequest(),
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Trigger a manual run of the auto-apply job."""
    try:
        user_id = _get_current_user_id()
        result = await scheduler.trigger_manual_run(user_id, request.max_applications)
        return result
    except Exception as e:
        logger.error(f"Failed to trigger manual run: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger manual run: {e}")


@router.post("/stop")
async def stop_running_job(
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Stop the currently running auto-apply job."""
    try:
        user_id = _get_current_user_id()
        cancelled = await scheduler.cancel_running_job(user_id)
        
        if cancelled:
            return {"status": "success", "message": "Cancellation requested"}
        else:
            return {"status": "info", "message": "No running job to cancel"}
    except Exception as e:
        logger.error(f"Failed to stop running job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop job: {e}")


@router.get("/history", response_model=RunHistoryResponse)
async def get_run_history(
    limit: int = Query(default=20, le=100),
    scheduler: SchedulerService = Depends(get_scheduler_service)
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
                error_message=run.error_message
            )
            for run in runs
        ]
        
        return RunHistoryResponse(
            runs=history_items,
            total_count=len(history_items)
        )
    except Exception as e:
        logger.error(f"Failed to get run history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get run history: {e}")

