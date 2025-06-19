"""Database connection and storage utilities."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# Database connection setup
DATABASE_URL = settings.database_url
engine: AsyncEngine = create_async_engine(str(DATABASE_URL), echo=True)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# Base class for declarative models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Token storage utility
class TokenStorage:
    """Utility class for token operations."""

    @staticmethod
    async def init_models() -> None:
        """Initialize database models."""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def save(token_data: dict) -> "Token":
        """Save a new token, replacing any existing ones."""
        from app.models.token import Token

        async with async_session() as session:
            # Clear previous tokens
            await session.execute(Token.__table__.delete())
            tok = Token(**token_data)
            session.add(tok)
            await session.commit()
            await session.refresh(tok)
            return tok

    @staticmethod
    async def get_latest() -> "Token | None":
        """Get the most recent token."""
        from app.models.token import Token

        async with async_session() as session:
            result = await session.execute(
                Token.__table__.select()
                .order_by(Token.obtained_at.desc())
                .limit(1)
            )
            row = result.first()
            return Token(**row._asdict()) if row else None