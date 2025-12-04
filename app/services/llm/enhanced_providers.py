import asyncio
import logging
from typing import Any

from anthropic import Anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancedClaudeProvider:
    """Enhanced Claude provider with job application specific methods."""

    def __init__(self, api_key: str | None = None):
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)

    async def generate(self, prompt: str) -> str:
        """Generate text with improved error handling."""
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model="claude-sonnet-4-20250514",
                system="You are a professional copywriter and career coach.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.2,
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise Exception(f"Failed to generate content: {e!s}")

    async def generate_cover_letter(
        self, vacancy: dict[str, Any], user_profile: dict[str, Any]
    ) -> str:
        """Generate a personalized cover letter."""
        company = vacancy.get("employer", {}).get("name", "the company")
        position = vacancy.get("name", "this position")
        requirements = vacancy.get("snippet", {}).get("requirement", "")
        responsibilities = vacancy.get("snippet", {}).get("responsibility", "")

        # Clean HTML from description if present
        description = vacancy.get("description", "")
        if description and "<" in description:
            import re

            description = re.sub(r"<[^>]+>", "", description)

        key_skills = [skill.get("name", "") for skill in vacancy.get("key_skills", [])]

        prompt = f"""Write a professional cover letter for this job application:

POSITION: {position}
COMPANY: {company}

JOB REQUIREMENTS:
{requirements}

KEY RESPONSIBILITIES:
{responsibilities}

REQUIRED SKILLS: {", ".join(key_skills) if key_skills else "Not specified"}

JOB DESCRIPTION:
{description[:800]}...

CANDIDATE PROFILE:
- Name: {user_profile.get("name", "Candidate")}
- Experience: {user_profile.get("experience", "Not specified")}
- Skills: {user_profile.get("skills", "Not specified")}
- Education: {user_profile.get("education", "Not specified")}
- Current Position: {user_profile.get("current_position", "Not specified")}
- Achievements: {user_profile.get("achievements", "Not specified")}

INSTRUCTIONS:
1. Write a concise, professional cover letter (300-400 words)
2. Address the hiring manager professionally
3. Highlight relevant experience matching job requirements
4. Show enthusiasm for the role
5. Include specific examples when possible
6. End with a strong call to action
7. Use professional but warm tone
8. Write in Russian if the job posting is in Russian
9. Use the candidate's actual information, not placeholders

Generate ONLY the cover letter text."""

        return await self.generate(prompt)

    async def answer_screening_questions(
        self,
        questions: list[dict[str, Any]],
        vacancy: dict[str, Any],
        user_profile: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generate answers for screening questions."""
        if not questions:
            return []

        questions_text = ""
        for i, q in enumerate(questions, 1):
            question_text = q.get("text", q.get("question", str(q)))
            questions_text += f"{i}. {question_text}\n"

        prompt = f"""Answer these job screening questions professionally:

JOB: {vacancy.get("name", "Position")} at {vacancy.get("employer", {}).get("name", "Company")}

CANDIDATE PROFILE:
- Experience: {user_profile.get("experience", "Not specified")}
- Skills: {user_profile.get("skills", "Not specified")}
- Education: {user_profile.get("education", "Not specified")}
- Current Role: {user_profile.get("current_position", "Not specified")}

QUESTIONS:
{questions_text}

INSTRUCTIONS:
1. Answer each question directly and professionally
2. Keep answers concise (2-3 sentences each)
3. Be honest based on the candidate profile
4. Show enthusiasm and professionalism
5. Format as: Answer 1: [answer], Answer 2: [answer], etc.

Provide only the numbered answers."""

        response = await self.generate(prompt)
        return self._parse_screening_answers(response, questions)

    def _parse_screening_answers(
        self, response: str, questions: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Parse LLM response into structured answers."""
        import re

        # Split by "Answer X:" pattern
        answer_pattern = r"Answer (\d+):\s*(.+?)(?=Answer \d+:|$)"
        matches = re.findall(answer_pattern, response, re.DOTALL)

        structured_answers = []

        for i, question in enumerate(questions):
            question_id = question.get("id", str(i))
            answer_text = ""

            # Find corresponding answer
            for match in matches:
                answer_num = int(match[0]) - 1
                if answer_num == i:
                    answer_text = match[1].strip()
                    break

            # Fallback answer
            if not answer_text:
                answer_text = "I am very interested in this opportunity and believe my experience would be valuable for this role."

            structured_answers.append({"id": question_id, "answer": answer_text})

        return structured_answers
