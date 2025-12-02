"""ApplyBot - Automated job application system for hh.ru."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.storage import TokenStorage
from app.routers import apply_router, auth_router, hh_apply
from app.routers.scheduler import router as scheduler_router
from app.services.scheduler_service import scheduler_service

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ApplyBot",
    description="Automated job application system for hh.ru",
    version="1.0.0",
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
    scheduler_status = scheduler_service.get_status()
    return {
        "status": "healthy",
        "service": "applybot",
        "scheduler": scheduler_status
    }


@app.on_event("startup")
async def startup_event():
    """Initialize application."""
    logger.info("Initializing application...")
    await TokenStorage.init_models()

    # Start scheduler if enabled
    if settings.scheduler_enabled:
        logger.info("Starting scheduler...")
        await scheduler_service.start()
        logger.info("Scheduler started successfully")

    logger.info("Application initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Stopping scheduler...")
    await scheduler_service.stop()
    logger.info("Application shutdown complete")
