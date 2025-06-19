from collections.abc import AsyncGenerator

from fastapi import Depends

from app.services.hh_client import HHClient
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider


async def hh_client_dep() -> AsyncGenerator[HHClient, None]:
    """Dependency for HH client"""
    client = HHClient()
    try:
        yield client
    finally:
        await client.client.aclose()


def llm_provider_dep(
    provider: LLMProvider = Depends(get_llm_provider),
) -> LLMProvider:
    """FastAPI dependency wrapper returning the chosen LLM provider."""
    return provider


# Additional convenience dependency for enhanced features
def enhanced_llm_dep() -> LLMProvider:
    """Get enhanced LLM provider with job application methods"""
    return get_llm_provider()
