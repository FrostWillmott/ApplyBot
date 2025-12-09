"""ApplyBot - Automated job application system for hh.ru."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.storage import TokenStorage
from app.routers import apply_router, auth_router, hh_apply
from app.routers.auto_reply import router as auto_reply_router
from app.routers.scheduler import router as scheduler_router
from app.services.auto_reply_service import auto_reply_service
from app.services.scheduler_service import scheduler_service

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Initializing application...")
    await TokenStorage.init_models()

    if settings.scheduler_enabled:
        logger.info("Starting scheduler...")
        await scheduler_service.start()
        logger.info("Scheduler started")

        logger.info("Starting auto-reply scheduler...")
        await auto_reply_service.start()
        logger.info("Auto-reply scheduler started")

    logger.info("Application initialized")

    yield

    logger.info("Shutting down...")
    await scheduler_service.stop()
    await auto_reply_service.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="ApplyBot",
    description="Automated job application system for hh.ru",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(apply_router)
app.include_router(hh_apply.router)
app.include_router(scheduler_router)
app.include_router(auto_reply_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Serve the frontend application."""
    return FileResponse("app/static/index.html")


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "message": "ApplyBot API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "active",
        "scheduler_enabled": settings.scheduler_enabled,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "applybot",
        "scheduler": scheduler_service.get_status(),
        "auto_reply": auto_reply_service.get_status(),
    }
