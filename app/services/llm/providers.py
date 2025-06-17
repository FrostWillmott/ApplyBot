import asyncio

from anthropic import Anthropic


class ClaudeProvider:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        # Вызываем blocking API в отдельном потоке
        response = await asyncio.to_thread(
            self.client.messages.create,
            model="claude-sonnet-4-20250514",
            system="You are a professional copywriter.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.2,
        )
        # Anthropic Messages API возвращает List[TextBlock] в response.content
        # Берём первый TextBlock и достаём его .text
        return response.content[0].text.strip()
