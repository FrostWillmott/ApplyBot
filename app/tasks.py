from redis import Redis
from rq import Queue

from .services.claude_client import ClaudeClient
from .services.hh_client import HHClient

# соединение с Redis
redis_conn = Redis.from_url("redis://redis:6379/0")
q = Queue("applybot", connection=redis_conn)


def enqueue_apply(vacancy_id: str, user_profile: dict):
    """Ставим в очередь задачу генерации письма и отправки отклика."""
    q.enqueue(process_apply, vacancy_id, user_profile)


def process_apply(vacancy_id: str, user_profile: dict):
    """Фоновая задача: генерируем письмо и отправляем отклик."""
    import asyncio

    async def _inner():
        hh = HHClient()
        vacancy = await hh.client.get(f"/vacancies/{vacancy_id}")
        vacancy.raise_for_status()
        vacancy = vacancy.json()
        letter = await ClaudeClient.generate_cover_letter(
            vacancy, user_profile
        )
        result = await hh.apply(vacancy_id, letter)
        return result

    # запускаем в собственном event loop
    return asyncio.run(_inner())
