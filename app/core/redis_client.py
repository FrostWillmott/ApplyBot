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


class ProcessedVacancyCache:
    """Cache for processed vacancy IDs to avoid re-downloading.

    Stores vacancy IDs that have been seen/processed with TTL.
    This helps avoid repeatedly downloading and filtering the same vacancies.
    """

    PREFIX = "processed_vacancy:"
    TTL_SECONDS = 86400 * 7  # 7 days - vacancies change rarely

    @classmethod
    async def add_many(cls, vacancy_ids: list[str]) -> None:
        """Add multiple vacancy IDs to cache."""
        if not vacancy_ids:
            return
        redis = await get_redis()
        pipe = redis.pipeline()
        for vid in vacancy_ids:
            key = f"{cls.PREFIX}{vid}"
            pipe.setex(key, cls.TTL_SECONDS, "1")
        await pipe.execute()
        logger.debug(f"Cached {len(vacancy_ids)} processed vacancy IDs")

    @classmethod
    async def is_processed(cls, vacancy_id: str) -> bool:
        """Check if vacancy ID was already processed."""
        redis = await get_redis()
        key = f"{cls.PREFIX}{vacancy_id}"
        return await redis.exists(key) > 0

    @classmethod
    async def filter_new(cls, vacancy_ids: list[str]) -> list[str]:
        """Filter out already processed vacancy IDs, return only new ones."""
        if not vacancy_ids:
            return []
        redis = await get_redis()
        pipe = redis.pipeline()
        for vid in vacancy_ids:
            key = f"{cls.PREFIX}{vid}"
            pipe.exists(key)
        results = await pipe.execute()
        new_ids = [
            vid for vid, exists in zip(vacancy_ids, results, strict=False) if not exists
        ]
        logger.debug(
            f"Filtered {len(vacancy_ids)} IDs: {len(new_ids)} new, "
            f"{len(vacancy_ids) - len(new_ids)} already processed"
        )
        return new_ids

    @classmethod
    async def get_stats(cls) -> dict:
        """Get cache statistics."""
        redis = await get_redis()
        # Count keys with our prefix (for debugging)
        cursor = 0
        count = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=f"{cls.PREFIX}*", count=1000)
            count += len(keys)
            if cursor == 0:
                break
        return {"cached_vacancy_ids": count}
