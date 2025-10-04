"""
ApplyBot - Automated job application system for hh.ru

This is the main entry point for the FastAPI application.
It sets up the app, middleware, routers, and startup/shutdown events.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.storage import TokenStorage
from app.routers import auth_router
from app.routers.mvp import router as mvp_router
from app.services.hh_client import HHClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ApplyBot",
    description="Automated job application system for hh.ru",
    version="1.0.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(mvp_router)


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "message": "ApplyBot API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "active",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "applybot"}


async def _auto_apply_once(max_to_apply: int) -> int:
    """Perform one auto-apply pass and return how many successful applications were made."""
    applied = 0
    client = HHClient()
    try:
        # Get first resume
        resumes = await client.get_my_resumes()
        items = resumes if isinstance(resumes, list) else resumes.get("items", [])
        if not items:
            logger.warning("Auto-apply: нет доступных резюме — пропуск итерации")
            return 0
        resume_id = items[0]["id"]

        # Search remote-only Python vacancies
        search = await client.search_vacancies(
            text="Python разработчик",
            page=0,
            per_page=min(50, max_to_apply),
            schedule="remote",
        )
        vacancies = search.get("items", [])
        if not vacancies:
            logger.info("Auto-apply: вакансии не найдены")
            return 0

        # Apply without cover letters; skip on any error
        for v in vacancies[:max_to_apply]:
            vid = v.get("id")
            if not vid:
                continue
            try:
                await client.apply(vacancy_id=vid, resume_id=resume_id, cover_letter=None)
                applied += 1
            except Exception as e:
                logger.info(f"Auto-apply: пропуск вакансии {vid}: {e}")
        return applied
    finally:
        await client.close()


async def _auto_apply_worker():
    interval_min = int(os.getenv("AUTO_APPLY_INTERVAL_MIN", "15"))
    daily_limit = int(os.getenv("AUTO_DAILY_LIMIT", "100"))

    applied_today = 0
    current_day = datetime.utcnow().date()

    logger.info(
        f"Auto-apply worker запущен: interval={interval_min}m, daily_limit={daily_limit}"
    )

    while True:
        try:
            # reset daily counter at UTC midnight
            now_day = datetime.utcnow().date()
            if now_day != current_day:
                current_day = now_day
                applied_today = 0
                logger.info("Auto-apply: дневной счётчик обнулён")

            remaining = max(0, daily_limit - applied_today)
            if remaining > 0:
                made = await _auto_apply_once(remaining)
                applied_today += made
                logger.info(f"Auto-apply: выполнено {made}, всего сегодня {applied_today}/{daily_limit}")
            else:
                logger.info("Auto-apply: дневной лимит исчерпан, ожидание следующего дня")

        except Exception as loop_err:
            logger.error(f"Auto-apply: ошибка цикла: {loop_err}")

        # Sleep until next iteration
        await asyncio.sleep(max(1, interval_min) * 60)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database and other services on startup."""
    logger.info("Initializing application...")

    # Initialize database models
    await TokenStorage.init_models()

    # Start background auto-apply if enabled
    if os.getenv("ENABLE_AUTO_APPLY", "false").lower() in {"1", "true", "yes"}:
        app.state.auto_task = asyncio.create_task(_auto_apply_worker())
        logger.info("Background auto-apply task started")

    logger.info("Application initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application...")

    # Cancel background task if running
    task = getattr(app.state, "auto_task", None)
    if task:
        task.cancel()
        try:
            await task
        except Exception:
            pass

    logger.info("Application shutdown complete")
