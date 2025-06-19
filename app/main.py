"""
ApplyBot - Automated job application system for hh.ru

This is the main entry point for the FastAPI application.
It sets up the app, middleware, routers, and startup/shutdown events.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.storage import TokenStorage
from app.routers import apply_router, auth_router

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
app.include_router(apply_router)

# Mount static files
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
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "applybot"}


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database and other services on startup."""
    logger.info("Initializing application...")

    # Initialize database models
    await TokenStorage.init_models()

    logger.info("Application initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application...")
    # Close any open connections or resources
    logger.info("Application shutdown complete")
