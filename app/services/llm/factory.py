"""Factory for creating LLM providers."""

from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.providers import OllamaProvider


def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider instance."""
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
