"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_cover_letter(
        self, vacancy: dict[str, Any], user_profile: dict[str, Any]
    ) -> str:
        """Generate a cover letter for a job application.

        Args:
            vacancy: Vacancy details from HH.ru
            user_profile: User's profile information

        Returns:
            Generated cover letter text
        """
        pass

    @abstractmethod
    async def answer_screening_questions(
        self,
        questions: list[dict],
        vacancy: dict[str, Any],
        user_profile: dict[str, Any],
    ) -> list[dict]:
        """Answer screening questions for a job application.

        Args:
            questions: List of screening questions
            vacancy: Vacancy details
            user_profile: User's profile

        Returns:
            List of answers with question IDs
        """
        pass

    def _detect_language(self, text: str) -> str:
        """Detect if text is Russian or English."""
        cyrillic_count = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
        return "ru" if cyrillic_count > len(text) * 0.3 else "en"
