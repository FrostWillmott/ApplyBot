"""Shared test configuration and fixtures."""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.storage import Base, Token
from app.main import app
from app.schemas.apply import ApplyRequest, BulkApplyRequest


# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Create test database session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        hh_client_id="test_client_id",
        hh_client_secret="test_client_secret",
        hh_redirect_uri="http://localhost:8000/auth/callback",
        anthropic_api_key="test_anthropic_key",
        database_url="sqlite+aiosqlite:///./test.db",
    )


@pytest.fixture
def mock_hh_token(db_session):
    """Create mock HH token in database."""
    token = Token(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_in=3600,
        obtained_at=datetime.utcnow(),
    )
    db_session.add(token)
    db_session.commit()
    return token


@pytest.fixture
def sample_vacancy():
    """Sample vacancy data for testing."""
    return {
        "id": "12345",
        "name": "Python Developer",
        "employer": {"name": "Tech Corp"},
        "snippet": {
            "requirement": "Python, FastAPI, PostgreSQL",
            "responsibility": "Develop web applications",
        },
        "description": "We are looking for a skilled Python developer...",
        "key_skills": [{"name": "Python"}, {"name": "FastAPI"}],
        "questions": [
            {"id": "1", "text": "Why do you want to work here?"},
            {"id": "2", "text": "Describe your Python experience."},
        ],
    }


@pytest.fixture
def sample_apply_request():
    """Sample application request."""
    return ApplyRequest(
        position="Python Developer",
        resume="Experienced Python developer with 5+ years...",
        skills="Python, FastAPI, PostgreSQL, Docker",
        experience="5+ years in web development",
        resume_id="resume_123",
    )


@pytest.fixture
def sample_bulk_request():
    """Sample bulk application request."""
    return BulkApplyRequest(
        position="Python Developer",
        resume="Experienced Python developer with 5+ years...",
        skills="Python, FastAPI, PostgreSQL, Docker",
        experience="5+ years in web development",
        resume_id="resume_123",
        exclude_companies=["BadCorp"],
        salary_min=100000,
        remote_only=True,
    )


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    provider = AsyncMock()
    provider.generate.return_value = "Generated cover letter content"
    provider.generate_cover_letter.return_value = "Professional cover letter"
    provider.answer_screening_questions.return_value = [
        {"id": "1", "answer": "I'm passionate about technology"},
        {"id": "2", "answer": "5+ years of Python experience"},
    ]
    return provider


@pytest.fixture
def mock_hh_client():
    """Mock HH client for testing."""
    client = AsyncMock()
    client.search_vacancies.return_value = {
        "items": [
            {
                "id": "12345",
                "name": "Python Developer",
                "employer": {"name": "Tech Corp"},
            }
        ]
    }
    client.get_vacancy_details.return_value = {
        "id": "12345",
        "name": "Python Developer",
        "employer": {"name": "Tech Corp"},
        "description": "Job description...",
    }
    client.apply.return_value = {"status": "ok", "application_id": "app_123"}
    return client