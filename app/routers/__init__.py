"""API routers."""

from app.routers.apply import router as apply_router
from app.routers.auth import router as auth_router

__all__ = ["apply_router", "auth_router"]
