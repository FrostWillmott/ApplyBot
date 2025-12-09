import asyncio
import logging
import re
from typing import Any

from openai import APIError, APITimeoutError, OpenAI

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama LLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:14b",
    ):
        self.client = OpenAI(
            base_url=f"{base_url}/v1",
            api_key="ollama",  # Ollama doesn't require API key
            timeout=300.0,  # 5 minute timeout for CPU inference
        )
        self.model = model
        self.base_url = base_url

    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        try:
            logger.info(f"Calling Ollama at {self.base_url} with model {self.model}")
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional copywriter. /no_think",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.2,
            )
            if not response.choices:
                raise ValueError("Empty response from LLM")
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty content in response")
            logger.info(f"Ollama response received, length: {len(content)}")
            return content.strip()
        except ValueError:
            raise
        except APITimeoutError as e:
            logger.error(f"LLM timeout: {e}")
            raise ValueError("LLM request timed out") from e
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise ValueError(f"LLM API error: {e!s}") from e

    async def generate_cover_letter(
        self, vacancy: dict[str, Any], user_profile: dict[str, Any]
    ) -> str:
        """Generate a cover letter for a job vacancy."""
        company = vacancy.get("employer", {}).get("name", "the company")
        position = vacancy.get("name", "this position")
        requirements = vacancy.get("snippet", {}).get("requirement", "")
        responsibilities = vacancy.get("snippet", {}).get("responsibility", "")
        description = vacancy.get("description", "")
        if description and "<" in description:
            description = re.sub(r"<[^>]+>", "", description)

        key_skills = [skill.get("name", "") for skill in vacancy.get("key_skills", [])]

        is_russian = any(
            char in (requirements + responsibilities + description)
            for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        )

        candidate_name = user_profile.get("name", "Кандидат")
        candidate_email = user_profile.get("email", "")

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
- Имя: {candidate_name}
- Email: {candidate_email}
- Опыт: {user_profile.get("experience", "Не указан")}
- Навыки: {user_profile.get("skills", "Не указаны")}
- Образование: {user_profile.get("education", "Не указано")}
- Текущая должность: {user_profile.get("position", "Не указана")}

ИНСТРУКЦИИ:
1. Напишите краткое, профессиональное сопроводительное письмо (200-300 слов)
2. Начните с обращения "Здравствуйте!" или "Добрый день!"
3. Выделите релевантный опыт, соответствующий требованиям вакансии
4. Покажите энтузиазм к должности и компании
5. Включите конкретные примеры из опыта кандидата
6. Завершите подписью с РЕАЛЬНЫМ именем кандидата ({candidate_name}) и email ({candidate_email})
7. Используйте профессиональный, но теплый тон

ВАЖНО:
- НЕ используйте плейсхолдеры вроде [Ваш email], [Дата], [Имя менеджера]
- НЕ добавляйте примечания или комментарии после письма
- Используйте ТОЛЬКО реальные данные кандидата из профиля выше
- Выводите ТОЛЬКО текст письма, ничего больше

Сгенерируйте сопроводительное письмо:"""
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
- Name: {candidate_name}
- Email: {candidate_email}
- Experience: {user_profile.get("experience", "Not specified")}
- Skills: {user_profile.get("skills", "Not specified")}
- Education: {user_profile.get("education", "Not specified")}
- Current Position: {user_profile.get("position", "Not specified")}

INSTRUCTIONS:
1. Write a concise, professional cover letter (200-300 words)
2. Start with "Dear Hiring Manager," or similar professional greeting
3. Highlight relevant experience matching job requirements
4. Show enthusiasm for the role and company
5. Include specific examples from candidate's experience
6. End with signature using the REAL candidate name ({candidate_name}) and email ({candidate_email})
7. Use professional but warm tone

IMPORTANT:
- Do NOT use placeholders like [Your email], [Date], [Manager name]
- Do NOT add notes or comments after the letter
- Use ONLY real candidate data from the profile above
- Output ONLY the cover letter text, nothing else

Generate the cover letter:"""

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

        questions_text = ""
        for i, q in enumerate(questions, 1):
            question_text = q.get("text", q.get("question", str(q)))
            questions_text += f"{i}. {question_text}\n"

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
        """Parse LLM response into structured answers."""
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

            for match in matches:
                answer_num = int(match[0]) - 1
                if answer_num == i:
                    answer_text = match[1].strip()
                    break

            if not answer_text:
                sample_text = str(question)
                is_russian = any(
                    char in sample_text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                )

                if is_russian:
                    answer_text = "Я очень заинтересован в этой возможности и считаю, что мой опыт будет ценным для этой роли."
                else:
                    answer_text = "I am very interested in this opportunity and believe my experience would be valuable for this role."

            structured_answers.append({"id": question_id, "answer": answer_text})

        return structured_answers
