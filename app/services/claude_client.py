import os

from anthropic import AI_PROMPT, HUMAN_PROMPT, Anthropic


class ClaudeClient:
    """Обёртка над Anthropic API для работы с моделью Claude Sonnet 4."""

    def __init__(self, api_key: str | None = None):
        # Клиент возьмёт ключ из переменной окружения, если не передали явно
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=key)

    async def generate_cover_letter(
        self,
        prompt: str,
        model: str = "claude-sonnet-4",
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> str:
        """Генерирует сопроводительное письмо по заданному prompt."""
        # Собираем сообщения в формате Messages API
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": HUMAN_PROMPT + prompt + AI_PROMPT},
        ]

        # Отправляем запрос
        resp = await self.client.messages.create(
            model=model,
            messages=messages,
            max_tokens_to_sample=max_tokens,
            temperature=temperature,
        )

        # Возвращаем чистый текст ответа
        return resp.completion.strip()
