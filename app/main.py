from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.apply import router as apply_router
from app.routers.auth import router as auth_router

app = FastAPI(
    title="ApplyBot",
    description="Automated job application system for hh.ru",
    version="1.0.0"
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


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ApplyBot API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "active"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "applybot"}


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database and other services on startup."""
    from app.core.storage import TokenStorage
    await TokenStorage.init_models()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    pass