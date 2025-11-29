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

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )


settings = Settings()
