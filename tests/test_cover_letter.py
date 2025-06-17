import os

import pytest
from fastapi.testclient import TestClient

from app.main import app  # Импортируйте ваше FastAPI приложение
from app.services.llm.providers import (
    ClaudeProvider,
)  # Импортируйте ваш провайдер

client = TestClient(app)


# Юнит-тесты с моками
@pytest.mark.asyncio
async def test_cover_letter_route_with_mock(monkeypatch):
    """Тест маршрута /cover-letter с моком генерации"""

    # Мокаем метод генерации
    async def fake_generate(self, prompt):
        return "Test letter content"

    monkeypatch.setattr(ClaudeProvider, "generate", fake_generate)

    # Тестовые данные
    test_data = {
        "job_title": "Software Engineer",
        "company": "Tech Corp",
        "skills": "Python, AI",
        "experience": "5 years",
    }

    # Вызов эндпоинта
    response = client.post("/cover-letter", json=test_data)

    # Проверки
    assert response.status_code == 200
    assert response.json() == {"letter": "Test letter content"}


@pytest.mark.asyncio
async def test_apply_route_with_mock(monkeypatch):
    """Тест маршрута /apply с моком генерации"""

    # Мокаем метод генерации
    async def fake_generate(self, prompt):
        return "Mocked application content"

    monkeypatch.setattr(ClaudeProvider, "generate", fake_generate)

    # Тестовые данные
    test_data = {
        "position": "Data Scientist",
        "company_info": "AI research lab",
        "resume": "Experienced ML engineer",
    }

    # Вызов эндпоинта
    response = client.post("/apply", json=test_data)

    # Проверки
    assert response.status_code == 200
    assert "Mocked application content" in response.json()["response"]


# Интеграционные тесты (требуют реального ключа API)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_anthropic_integration():
    """Интеграционный тест с реальным API Anthropic"""

    # Получаем ключ из переменных окружения
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY не установлен")

    # Создаем реальный провайдер
    provider = ClaudeProvider(api_key=api_key)

    # Тестовый промпт
    test_prompt = "Напиши приветственное письмо на русском"

    # Вызов метода
    response = await provider.generate(test_prompt)

    # Проверки
    assert isinstance(response, str)
    assert len(response) > 20
    assert "привет" in response.lower()


@pytest.mark.integration
def test_cover_letter_endpoint_integration():
    """End-to-end тест маршрута /cover-letter"""

    # Тестовые данные
    test_data = {
        "job_title": "Python Developer",
        "company": "ООО 'Технологии'",
        "skills": "FastAPI, PostgreSQL",
        "experience": "3+ года",
    }

    # Вызов эндпоинта
    response = client.post("/cover-letter", json=test_data)

    # Проверки
    assert response.status_code == 200
    response_data = response.json()
    assert "letter" in response_data
    content = response_data["letter"]

    assert isinstance(content, str)
    assert len(content) > 100
    assert "Python" in content
    assert "ООО 'Технологии'" in content


@pytest.mark.integration
def test_apply_endpoint_integration():
    """End-to-end тест маршрута /apply"""

    # Тестовые данные
    test_data = {
        "position": "ML Engineer",
        "company_info": "Стартап в области компьютерного зрения",
        "resume": "Опыт работы с нейронными сетями 4 года",
    }

    # Вызов эндпоинта
    response = client.post("/apply", json=test_data)

    # Проверки
    assert response.status_code == 200
    response_data = response.json()
    assert "response" in response_data
    content = response_data["response"]

    assert isinstance(content, str)
    assert len(content) > 150
    assert "ML Engineer" in content
    assert "компьютерного зрения" in content
