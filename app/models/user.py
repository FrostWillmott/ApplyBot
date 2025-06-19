import datetime
from sqlalchemy import DateTime, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.storage import Base


class User(Base):
    """Model for storing user information."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    
    # Relationships can be added here when needed
    # applications = relationship("ApplicationHistory", back_populates="user")
    
    class Config:
        orm_mode = True