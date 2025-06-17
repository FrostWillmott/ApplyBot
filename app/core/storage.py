import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings

# 1) Настройка движка и сессии
DATABASE_URL = settings.database_url  # уже строка вида postgresql+asyncpg://…
engine: AsyncEngine = create_async_engine(str(DATABASE_URL), echo=True)
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# 2) База для декларативного режима
class Base(DeclarativeBase):
    pass


# 3) Модель Token без @dataclass
class Token(Base):
    __tablename__ = "hh_tokens"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_in: Mapped[int] = mapped_column(Integer, nullable=False)
    obtained_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    def is_expired(self) -> bool:
        return (
            datetime.datetime.utcnow()
            > self.obtained_at + datetime.timedelta(seconds=self.expires_in)
        )


# 4) Хранилище
class TokenStorage:
    @staticmethod
    async def init_models() -> None:
        # создаём таблицу при старте
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def save(token_data: dict) -> Token:
        async with async_session() as session:
            # очищаем предыдущие токены
            await session.execute(Token.__table__.delete())
            tok = Token(**token_data)
            session.add(tok)
            await session.commit()
            await session.refresh(tok)
            return tok

    @staticmethod
    async def get_latest() -> Token | None:
        async with async_session() as session:
            result = await session.execute(
                Token.__table__.select()
                .order_by(Token.obtained_at.desc())
                .limit(1)
            )
            row = result.first()
            return row[0] if row else None
