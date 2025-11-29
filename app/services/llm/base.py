from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        pass

    async def generate_cover_letter(
        self, vacancy: dict[str, Any], user_profile: dict[str, Any]
    ) -> str:
        """Generate a cover letter for a job vacancy."""
        company = vacancy.get("employer", {}).get("name", "the company")
        position = vacancy.get("name", "this position")

        prompt = f"""Write a professional cover letter for {position} at {company}.

Candidate details: {user_profile.get("experience", "N/A")}
Skills: {user_profile.get("skills", "N/A")}

Generate a concise, professional cover letter."""

        return await self.generate(prompt)

    async def answer_screening_questions(
        self,
        questions: list[dict[str, Any]],
        vacancy: dict[str, Any],
        user_profile: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generate answers for job screening questions."""
        if not questions:
            return []

        answers = []
        for i, question in enumerate(questions):
            question_text = question.get("text", str(question))

            prompt = f"""Answer this job screening question professionally:

Question: {question_text}

Candidate profile: {user_profile.get("experience", "N/A")}

Provide a brief, professional answer."""

            answer = await self.generate(prompt)
            answers.append(
                {"id": question.get("id", str(i)), "answer": answer.strip()}
            )

        return answers
