from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.providers import ClaudeProvider


def get_llm_provider() -> LLMProvider:
    return ClaudeProvider(settings.anthropic_api_key)
