from typing import Literal

from pydantic import AnyUrl, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hh_client_id: str
    hh_client_secret: str
    hh_redirect_uri: str
    llm_provider: Literal["sonnet4"] = "sonnet4"
    anthropic_api_key: str
    database_url: AnyUrl

    # Cookie settings
    cookie_secure: bool = True  # Set to False only for local HTTP development

    # Scheduler settings
    scheduler_enabled: bool = True
    scheduler_default_hour: int = 9
    scheduler_default_minute: int = 0
    scheduler_default_days: str = "mon,tue,wed,thu,fri"
    scheduler_default_timezone: str = "Europe/Moscow"
    scheduler_max_applications: int = 20
    scheduler_auto_start: bool = True

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )


settings = Settings()
