import asyncio
import logging
import re
from typing import Any

from anthropic import Anthropic

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """Enhanced Claude provider with job application capabilities"""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt (original method)"""
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model="claude-sonnet-4-20250514",
                system="You are a professional copywriter.",
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
        """Generate a personalized cover letter for a job vacancy"""
        company = vacancy.get("employer", {}).get("name", "the company")
        position = vacancy.get("name", "this position")

        # Extract job information
        requirements = vacancy.get("snippet", {}).get("requirement", "")
        responsibilities = vacancy.get("snippet", {}).get("responsibility", "")

        # Clean HTML from description if present
        description = vacancy.get("description", "")
        if description and "<" in description:
            description = re.sub(r"<[^>]+>", "", description)

        key_skills = [
            skill.get("name", "") for skill in vacancy.get("key_skills", [])
        ]

        # Determine language based on job posting
        is_russian = any(
            char in (requirements + responsibilities + description)
            for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        )

        if is_russian:
            prompt = f"""Напишите профессиональное сопроводительное письмо для данной вакансии:

ДОЛЖНОСТЬ: {position}
КОМПАНИЯ: {company}

ТРЕБОВАНИЯ К КАНДИДАТУ:
{requirements}

ОСНОВНЫЕ ОБЯЗАННОСТИ:
{responsibilities}

КЛЮЧЕВЫЕ НАВЫКИ: {", ".join(key_skills) if key_skills else "Не указаны"}

ОПИСАНИЕ ВАКАНСИИ:
{description[:800]}...

ПРОФИЛЬ КАНДИДАТА:
- Имя: {user_profile.get("name", "Кандидат")}
- Опыт: {user_profile.get("experience", "Не указан")}
- Навыки: {user_profile.get("skills", "Не указаны")}
- Образование: {user_profile.get("education", "Не указано")}
- Текущая должность: {user_profile.get("current_position", "Не указана")}
- Достижения: {user_profile.get("achievements", "Не указаны")}

ИНСТРУКЦИИ:
1. Напишите краткое, профессиональное сопроводительное письмо (300-400 слов)
2. Обратитесь к менеджеру по найму профессионально
3. Выделите релевантный опыт, соответствующий требованиям вакансии
4. Покажите энтузиазм к должности и компании
5. Включите конкретные примеры, когда это возможно
6. Завершите убедительным призывом к действию
7. Используйте профессиональный, но теплый тон
8. Используйте реальную информацию кандидата, а не заглушки

Сгенерируйте ТОЛЬКО текст сопроводительного письма."""
        else:
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
4. Show enthusiasm for the role and company
5. Include specific examples when possible
6. End with a strong call to action
7. Use professional but warm tone
8. Use the candidate's actual information, not placeholders

Generate ONLY the cover letter text."""

        return await self.generate(prompt)

    async def answer_screening_questions(
        self,
        questions: list[dict[str, Any]],
        vacancy: dict[str, Any],
        user_profile: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generate answers for job screening questions"""
        if not questions:
            return []

        questions_text = ""
        for i, q in enumerate(questions, 1):
            question_text = q.get("text", q.get("question", str(q)))
            questions_text += f"{i}. {question_text}\n"

        # Determine language
        sample_text = questions_text + vacancy.get("name", "")
        is_russian = any(
            char in sample_text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        )

        if is_russian:
            prompt = f"""Ответьте на эти вопросы работодателя профессионально:

ВАКАНСИЯ: {vacancy.get("name", "Должность")} в {vacancy.get("employer", {}).get("name", "Компании")}

ПРОФИЛЬ КАНДИДАТА:
- Опыт: {user_profile.get("experience", "Не указан")}
- Навыки: {user_profile.get("skills", "Не указаны")}
- Образование: {user_profile.get("education", "Не указано")}
- Текущая роль: {user_profile.get("current_position", "Не указана")}

ВОПРОСЫ:
{questions_text}

ИНСТРУКЦИИ:
1. Отвечайте на каждый вопрос прямо и профессионально
2. Делайте ответы краткими (2-3 предложения на вопрос)
3. Будьте честными, основываясь на профиле кандидата
4. Показывайте энтузиазм и профессионализм
5. Форматируйте как: Ответ 1: [ответ], Ответ 2: [ответ], и т.д.

Предоставьте только пронумерованные ответы."""
        else:
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
        """Parse LLM response into structured answers"""
        # Handle both Russian and English formats
        answer_patterns = [
            r"(?:Answer|Ответ) (\d+):\s*(.+?)(?=(?:Answer|Ответ) \d+:|$)",
            r"(\d+)\.\s*(.+?)(?=\d+\.|$)",
        ]

        matches = []
        for pattern in answer_patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                break

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
                # Determine language for fallback
                sample_text = str(question)
                is_russian = any(
                    char in sample_text
                    for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                )

                if is_russian:
                    answer_text = "Я очень заинтересован в этой возможности и считаю, что мой опыт будет ценным для этой роли."
                else:
                    answer_text = "I am very interested in this opportunity and believe my experience would be valuable for this role."

            structured_answers.append(
                {"id": question_id, "answer": answer_text}
            )

        return structured_answers
