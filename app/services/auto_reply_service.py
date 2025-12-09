"""Auto-reply service for handling recruiter messages."""

import asyncio
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.storage import async_session
from app.models.scheduler import AutoReplyHistory, AutoReplySettings
from app.services.hh_client import HHClient
from app.services.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """Get current time as UTC naive datetime for DB storage."""
    return datetime.now(UTC).replace(tzinfo=None)


class AutoReplyService:
    """Service for automatically replying to recruiter messages."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._scheduler: AsyncIOScheduler | None = None
        self._running_checks: dict[str, bool] = {}

    async def start(self):
        """Start the auto-reply scheduler."""
        if self._scheduler is not None and self._scheduler.running:
            logger.info("Auto-reply scheduler already running")
            return

        self._scheduler = AsyncIOScheduler(timezone=settings.scheduler_default_timezone)
        self._scheduler.start()
        logger.info("Auto-reply scheduler started")

        # Load all enabled user jobs
        await self._load_all_user_jobs()

    async def stop(self):
        """Stop the auto-reply scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Auto-reply scheduler stopped")

    async def _load_all_user_jobs(self):
        """Load and schedule all enabled auto-reply jobs."""
        async with async_session() as session:
            query = select(AutoReplySettings).where(AutoReplySettings.enabled)
            result = await session.execute(query)
            user_settings = result.scalars().all()

            for user_settings_item in user_settings:
                await self._schedule_user_job(user_settings_item)
                logger.info(
                    f"Loaded auto-reply job for user {user_settings_item.user_id}"
                )

    async def _schedule_user_job(self, user_settings: AutoReplySettings):
        """Schedule auto-reply check for a user."""
        if self._scheduler is None:
            return

        job_id = f"auto_reply_{user_settings.user_id}"

        # Remove existing job if any
        existing_job = self._scheduler.get_job(job_id)
        if existing_job:
            self._scheduler.remove_job(job_id)

        if not user_settings.enabled:
            return

        # Schedule with interval trigger
        trigger = IntervalTrigger(
            minutes=user_settings.check_interval_minutes,
            timezone=user_settings.timezone,
        )

        self._scheduler.add_job(
            self._run_auto_reply_check,
            trigger=trigger,
            id=job_id,
            args=[user_settings.user_id],
            replace_existing=True,
        )

        next_run = self._scheduler.get_job(job_id).next_run_time
        logger.info(
            f"Scheduled auto-reply for user {user_settings.user_id} "
            f"every {user_settings.check_interval_minutes} min, next run: {next_run}"
        )

    async def _run_auto_reply_check(self, user_id: str):
        """Execute auto-reply check for a user."""
        if self._running_checks.get(user_id):
            logger.warning(f"Auto-reply check already running for user {user_id}")
            return

        self._running_checks[user_id] = True

        try:
            logger.info(f"Starting auto-reply check for user {user_id}")

            async with async_session() as session:
                query = select(AutoReplySettings).where(
                    AutoReplySettings.user_id == user_id
                )
                result = await session.execute(query)
                user_settings = result.scalar_one_or_none()

                if not user_settings or not user_settings.enabled:
                    logger.info(f"Auto-reply disabled for user {user_id}")
                    return

                # Check if we're within active hours
                if not self._is_active_time(user_settings):
                    logger.info(
                        f"Outside active hours for user {user_id}, skipping check"
                    )
                    return

            # Check for unread messages and process them
            processed, replied = await self._process_unread_messages(
                user_id, user_settings.auto_send
            )

            # Update statistics
            async with async_session() as session:
                await session.execute(
                    update(AutoReplySettings)
                    .where(AutoReplySettings.user_id == user_id)
                    .values(
                        last_check_at=_now(),
                        total_messages_processed=AutoReplySettings.total_messages_processed
                        + processed,
                        total_replies_sent=AutoReplySettings.total_replies_sent
                        + replied,
                    )
                )
                await session.commit()

            logger.info(
                f"Auto-reply check completed for {user_id}: "
                f"processed={processed}, replied={replied}"
            )

        except httpx.RequestError as e:
            logger.error(f"Network error during auto-reply check for {user_id}: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Database error during auto-reply check for {user_id}: {e}")
        except ValueError as e:
            logger.error(f"Validation error during auto-reply check for {user_id}: {e}")
        finally:
            self._running_checks[user_id] = False

    def _is_active_time(self, settings: AutoReplySettings) -> bool:
        """Check if current time is within active hours."""
        try:
            tz = ZoneInfo(settings.timezone)
            now = datetime.now(tz)

            # Check day of week
            day_map = {
                0: "mon",
                1: "tue",
                2: "wed",
                3: "thu",
                4: "fri",
                5: "sat",
                6: "sun",
            }
            current_day = day_map[now.weekday()]
            active_days = settings.active_days.lower().split(",")

            if current_day not in active_days:
                return False

            # Check hour
            if not (
                settings.active_hours_start <= now.hour < settings.active_hours_end
            ):
                return False

            return True
        except Exception as e:
            logger.warning(f"Error checking active time: {e}")
            return True  # Default to active if check fails

    async def _process_unread_messages(
        self, user_id: str, auto_send: bool
    ) -> tuple[int, int]:
        """Process unread messages and generate/send replies.

        Returns:
            Tuple of (processed_count, replied_count)
        """
        hh_client = HHClient()
        llm_provider = get_llm_provider()
        processed = 0
        replied = 0

        try:
            # Get negotiations with unread messages
            negotiations = await hh_client.get_negotiations_with_unread()

            for negotiation in negotiations:
                negotiation_id = str(negotiation.get("id", ""))
                if not negotiation_id:
                    continue

                # Get messages for this negotiation
                messages = await hh_client.get_negotiation_messages(negotiation_id)
                if not messages:
                    continue

                # Find the last message from employer (not from us)
                last_employer_message = None
                for msg in reversed(messages):
                    # Check if message is from employer
                    author = msg.get("author", {})
                    if author.get("participant_type") == "employer":
                        last_employer_message = msg
                        break

                if not last_employer_message:
                    continue

                # Check if we've already replied to this message
                message_text = last_employer_message.get("text", "")
                if await self._already_replied(negotiation_id, message_text):
                    continue

                processed += 1

                # Get vacancy info for context
                vacancy = negotiation.get("vacancy", {})
                employer = vacancy.get("employer", {})

                # Generate reply using LLM
                reply = await self._generate_reply(
                    llm_provider,
                    message_text,
                    vacancy,
                    messages,
                )

                if not reply:
                    continue

                # Save to history
                await self._save_reply_history(
                    user_id=user_id,
                    negotiation_id=negotiation_id,
                    vacancy_id=str(vacancy.get("id", "")),
                    employer_message=message_text,
                    generated_reply=reply,
                    was_sent=auto_send,
                    employer_name=employer.get("name"),
                    vacancy_title=vacancy.get("name"),
                )

                # Send if auto_send is enabled
                if auto_send:
                    result = await hh_client.send_negotiation_message(
                        negotiation_id, reply
                    )
                    if result:
                        replied += 1
                        logger.info(
                            f"Auto-replied to negotiation {negotiation_id}: "
                            f"{vacancy.get('name')}"
                        )

                # Small delay between processing
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error processing unread messages: {e}")

        return processed, replied

    async def _already_replied(
        self, negotiation_id: str, employer_message: str
    ) -> bool:
        """Check if we've already replied to this specific message."""
        try:
            async with async_session() as session:
                query = select(AutoReplyHistory).where(
                    AutoReplyHistory.negotiation_id == negotiation_id,
                    AutoReplyHistory.employer_message == employer_message,
                )
                result = await session.execute(query)
                return result.scalar_one_or_none() is not None
        except SQLAlchemyError:
            return False

    async def _generate_reply(
        self,
        llm_provider,
        employer_message: str,
        vacancy: dict,
        conversation_history: list[dict],
    ) -> str | None:
        """Generate a reply using LLM."""
        try:
            # Build conversation context
            conversation_text = ""
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                author = msg.get("author", {})
                participant_type = author.get("participant_type", "unknown")
                text = msg.get("text", "")
                if participant_type == "employer":
                    conversation_text += f"Рекрутер: {text}\n"
                else:
                    conversation_text += f"Я: {text}\n"

            vacancy_title = vacancy.get("name", "Вакансия")
            company = vacancy.get("employer", {}).get("name", "Компания")

            # Russian prompt for recruiter message reply
            prompt = f"""Ты помогаешь соискателю отвечать на сообщения рекрутеров на hh.ru.

ВАКАНСИЯ: {vacancy_title} в {company}

ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_text}

ПОСЛЕДНЕЕ СООБЩЕНИЕ РЕКРУТЕРА:
{employer_message}

ИНСТРУКЦИИ:
1. Напиши профессиональный и вежливый ответ
2. Ответ должен быть кратким (2-4 предложения)
3. Покажи заинтересованность в вакансии
4. Если рекрутер задает вопрос - ответь на него
5. Если приглашают на собеседование - подтверди готовность
6. Используй "Добрый день!" в начале, если уместно
7. НЕ добавляй подпись с именем или контактами
8. Пиши ТОЛЬКО текст ответа, без пояснений

Ответ:"""

            response = await llm_provider.generate(prompt)
            return response.strip() if response else None

        except Exception as e:
            logger.error(f"Error generating reply: {e}")
            return None

    async def _save_reply_history(
        self,
        user_id: str,
        negotiation_id: str,
        vacancy_id: str,
        employer_message: str,
        generated_reply: str,
        was_sent: bool,
        employer_name: str | None,
        vacancy_title: str | None,
    ) -> None:
        """Save reply to history."""
        try:
            async with async_session() as session:
                history = AutoReplyHistory(
                    user_id=user_id,
                    negotiation_id=negotiation_id,
                    vacancy_id=vacancy_id,
                    employer_message=employer_message,
                    generated_reply=generated_reply,
                    was_sent=was_sent,
                    employer_name=employer_name,
                    vacancy_title=vacancy_title,
                )
                session.add(history)
                await session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Failed to save reply history: {e}")

    async def update_user_settings(
        self, user_id: str, enabled: bool, **kwargs
    ) -> AutoReplySettings:
        """Update or create auto-reply settings for a user."""
        async with async_session() as session:
            query = select(AutoReplySettings).where(
                AutoReplySettings.user_id == user_id
            )
            result = await session.execute(query)
            user_settings = result.scalar_one_or_none()

            if user_settings:
                # Update existing
                for key, value in kwargs.items():
                    if hasattr(user_settings, key) and value is not None:
                        setattr(user_settings, key, value)
                user_settings.enabled = enabled
                user_settings.updated_at = _now()
            else:
                # Create new
                user_settings = AutoReplySettings(
                    user_id=user_id,
                    enabled=enabled,
                    **{k: v for k, v in kwargs.items() if v is not None},
                )
                session.add(user_settings)

            await session.commit()
            await session.refresh(user_settings)

            # Update scheduler
            await self._schedule_user_job(user_settings)

            return user_settings

    async def get_user_settings(self, user_id: str) -> AutoReplySettings | None:
        """Get auto-reply settings for a user."""
        async with async_session() as session:
            query = select(AutoReplySettings).where(
                AutoReplySettings.user_id == user_id
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_reply_history(
        self, user_id: str, limit: int = 20
    ) -> list[AutoReplyHistory]:
        """Get auto-reply history for a user."""
        async with async_session() as session:
            query = (
                select(AutoReplyHistory)
                .where(AutoReplyHistory.user_id == user_id)
                .order_by(AutoReplyHistory.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def trigger_manual_check(self, user_id: str) -> dict:
        """Trigger a manual auto-reply check."""
        if self._running_checks.get(user_id):
            return {"status": "error", "message": "Check already running"}

        # Run in background
        asyncio.create_task(self._run_auto_reply_check(user_id))
        return {"status": "started", "message": "Auto-reply check started"}

    def get_status(self) -> dict:
        """Get auto-reply scheduler status."""
        if self._scheduler is None:
            return {"scheduler_running": False, "jobs_count": 0}

        jobs = self._scheduler.get_jobs()
        return {
            "scheduler_running": self._scheduler.running,
            "jobs_count": len(jobs),
        }


# Global instance
auto_reply_service = AutoReplyService()


def get_auto_reply_service() -> AutoReplyService:
    """Get the auto-reply service instance."""
    return auto_reply_service
