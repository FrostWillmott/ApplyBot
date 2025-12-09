"""Application configuration management."""

from typing import Literal

from pydantic import AnyUrl, ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # HH.ru OAuth
    hh_client_id: str
    hh_client_secret: str
    hh_redirect_uri: str

    # LLM Configuration (Ollama)
    llm_provider: Literal["ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"

    # Database
    database_url: AnyUrl

    # Security
    cookie_secure: bool = Field(
        default=True,
        description="Set to False for local HTTP development",
    )

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_default_hour: int = Field(default=9, ge=0, le=23)
    scheduler_default_minute: int = Field(default=0, ge=0, le=59)
    scheduler_default_days: str = "mon,tue,wed,thu,fri"
    scheduler_default_timezone: str = "Europe/Moscow"
    scheduler_max_applications: int = Field(default=20, ge=1, le=100)
    scheduler_auto_start: bool = True

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
