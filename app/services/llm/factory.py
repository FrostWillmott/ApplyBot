"""Factory for creating LLM providers."""

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.providers import Sonnet4Provider


def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider instance."""
    if settings.llm_provider == "sonnet4":
        return Sonnet4Provider(api_key=settings.anthropic_api_key)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
