"""Redis client for state management with TTL."""

import logging

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Async Redis client
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


class OAuthStateStore:
    """OAuth state storage using Redis with automatic TTL expiration."""

    PREFIX = "oauth_state:"
    TTL_SECONDS = 600  # 10 minutes

    @classmethod
    async def set(cls, state: str, client_host: str) -> None:
        """Store OAuth state with TTL."""
        redis = await get_redis()
        key = f"{cls.PREFIX}{state}"
        await redis.setex(key, cls.TTL_SECONDS, client_host)
        logger.debug(f"Stored OAuth state: {state} (TTL: {cls.TTL_SECONDS}s)")

    @classmethod
    async def get(cls, state: str) -> str | None:
        """Get client host for OAuth state."""
        redis = await get_redis()
        key = f"{cls.PREFIX}{state}"
        return await redis.get(key)

    @classmethod
    async def exists(cls, state: str) -> bool:
        """Check if OAuth state exists."""
        redis = await get_redis()
        key = f"{cls.PREFIX}{state}"
        return await redis.exists(key) > 0

    @classmethod
    async def delete(cls, state: str) -> None:
        """Delete OAuth state."""
        redis = await get_redis()
        key = f"{cls.PREFIX}{state}"
        await redis.delete(key)
        logger.debug(f"Deleted OAuth state: {state}")
