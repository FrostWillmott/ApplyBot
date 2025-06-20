import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.storage import Base


class Token(Base):
    """Model for storing HH.ru API tokens."""

    __tablename__ = "hh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_in: Mapped[int] = mapped_column(Integer, nullable=False)
    obtained_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return (
                datetime.datetime.utcnow()
                > self.obtained_at + datetime.timedelta(seconds=self.expires_in)
        )
