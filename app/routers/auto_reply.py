"""API routes for auto-reply management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.services.auto_reply_service import AutoReplyService, get_auto_reply_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-reply", tags=["auto-reply"])

DEFAULT_USER_ID = "single_user"


def _get_current_user_id() -> str:
    """Get current user ID from session/token."""
    return DEFAULT_USER_ID


# Pydantic models for requests/responses
class AutoReplySettingsRequest(BaseModel):
    """Request model for updating auto-reply settings."""

    enabled: bool
    check_interval_minutes: int = 60
    active_hours_start: int = 9
    active_hours_end: int = 21
    active_days: str = "mon,tue,wed,thu,fri,sat,sun"
    auto_send: bool = False


class AutoReplySettingsResponse(BaseModel):
    """Response model for auto-reply settings."""

    enabled: bool
    check_interval_minutes: int
    active_hours_start: int
    active_hours_end: int
    active_days: str
    auto_send: bool
    last_check_at: str | None
    total_replies_sent: int
    total_messages_processed: int


class AutoReplyHistoryItem(BaseModel):
    """Response model for auto-reply history item."""

    id: int
    negotiation_id: str
    vacancy_id: str | None
    employer_message: str
    generated_reply: str
    was_sent: bool
    employer_name: str | None
    vacancy_title: str | None
    created_at: str


class AutoReplyStatusResponse(BaseModel):
    """Response model for auto-reply status."""

    scheduler_running: bool
    jobs_count: int
    settings: AutoReplySettingsResponse | None


@router.get("/status", response_model=AutoReplyStatusResponse)
async def get_auto_reply_status(
    service: AutoReplyService = Depends(get_auto_reply_service),
):
    """Get the current auto-reply scheduler status."""
    try:
        status = service.get_status()
        user_id = _get_current_user_id()
        user_settings = await service.get_user_settings(user_id)

        settings_response = None
        if user_settings:
            settings_response = AutoReplySettingsResponse(
                enabled=user_settings.enabled,
                check_interval_minutes=user_settings.check_interval_minutes,
                active_hours_start=user_settings.active_hours_start,
                active_hours_end=user_settings.active_hours_end,
                active_days=user_settings.active_days,
                auto_send=user_settings.auto_send,
                last_check_at=(
                    user_settings.last_check_at.isoformat()
                    if user_settings.last_check_at
                    else None
                ),
                total_replies_sent=user_settings.total_replies_sent,
                total_messages_processed=user_settings.total_messages_processed,
            )

        return AutoReplyStatusResponse(
            scheduler_running=status["scheduler_running"],
            jobs_count=status["jobs_count"],
            settings=settings_response,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting auto-reply status: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/settings", response_model=AutoReplySettingsResponse | None)
async def get_settings(
    service: AutoReplyService = Depends(get_auto_reply_service),
):
    """Get current user's auto-reply settings."""
    try:
        user_id = _get_current_user_id()
        user_settings = await service.get_user_settings(user_id)

        if not user_settings:
            return None

        return AutoReplySettingsResponse(
            enabled=user_settings.enabled,
            check_interval_minutes=user_settings.check_interval_minutes,
            active_hours_start=user_settings.active_hours_start,
            active_hours_end=user_settings.active_hours_end,
            active_days=user_settings.active_days,
            auto_send=user_settings.auto_send,
            last_check_at=(
                user_settings.last_check_at.isoformat()
                if user_settings.last_check_at
                else None
            ),
            total_replies_sent=user_settings.total_replies_sent,
            total_messages_processed=user_settings.total_messages_processed,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/settings", response_model=AutoReplySettingsResponse)
async def update_settings(
    request: AutoReplySettingsRequest,
    service: AutoReplyService = Depends(get_auto_reply_service),
):
    """Update auto-reply settings for the current user."""
    try:
        user_id = _get_current_user_id()

        user_settings = await service.update_user_settings(
            user_id=user_id,
            enabled=request.enabled,
            check_interval_minutes=request.check_interval_minutes,
            active_hours_start=request.active_hours_start,
            active_hours_end=request.active_hours_end,
            active_days=request.active_days,
            auto_send=request.auto_send,
        )

        status = "enabled" if request.enabled else "disabled"
        logger.info(f"Auto-reply settings updated for user {user_id}: {status}")

        return AutoReplySettingsResponse(
            enabled=user_settings.enabled,
            check_interval_minutes=user_settings.check_interval_minutes,
            active_hours_start=user_settings.active_hours_start,
            active_hours_end=user_settings.active_hours_end,
            active_days=user_settings.active_days,
            auto_send=user_settings.auto_send,
            last_check_at=(
                user_settings.last_check_at.isoformat()
                if user_settings.last_check_at
                else None
            ),
            total_replies_sent=user_settings.total_replies_sent,
            total_messages_processed=user_settings.total_messages_processed,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except ValueError as e:
        logger.error(f"Invalid settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/check")
async def trigger_manual_check(
    service: AutoReplyService = Depends(get_auto_reply_service),
):
    """Trigger a manual check for new messages."""
    try:
        user_id = _get_current_user_id()
        result = await service.trigger_manual_check(user_id)
        return result
    except SQLAlchemyError as e:
        logger.error(f"Database error triggering check: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/history", response_model=list[AutoReplyHistoryItem])
async def get_history(
    limit: int = Query(default=20, le=100),
    service: AutoReplyService = Depends(get_auto_reply_service),
):
    """Get auto-reply history for the current user."""
    try:
        user_id = _get_current_user_id()
        history = await service.get_reply_history(user_id, limit)

        return [
            AutoReplyHistoryItem(
                id=item.id,
                negotiation_id=item.negotiation_id,
                vacancy_id=item.vacancy_id,
                employer_message=item.employer_message,
                generated_reply=item.generated_reply,
                was_sent=item.was_sent,
                employer_name=item.employer_name,
                vacancy_title=item.vacancy_title,
                created_at=item.created_at.isoformat(),
            )
            for item in history
        ]
    except SQLAlchemyError as e:
        logger.error(f"Database error getting history: {e}")
        raise HTTPException(status_code=500, detail="Database error")
