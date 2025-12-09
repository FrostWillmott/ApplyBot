"""Pytest configuration and fixtures."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables before importing app modules
# Use direct assignment for LLM settings to override any .env values
os.environ.setdefault("HH_CLIENT_ID", "test_client_id")
os.environ.setdefault("HH_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("HH_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = "qwen3:14b"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SCHEDULER_ENABLED", "false")


@pytest.fixture
def sample_vacancy():
    """Sample vacancy data for testing."""
    return {
        "id": "12345",
        "name": "Python Developer",
        "employer": {"name": "Test Company", "id": "100"},
        "description": "We are looking for a Python developer with Django experience.",
        "snippet": {
            "requirement": "Python, Django, PostgreSQL required",
            "responsibility": "Develop backend services",
        },
        "key_skills": [{"name": "Python"}, {"name": "Django"}, {"name": "PostgreSQL"}],
        "archived": False,
        "relations": [],
        "salary": {"from": 100000, "to": 200000, "currency": "RUR"},
        "questions": [],
    }


@pytest.fixture
def sample_vacancy_with_questions():
    """Sample vacancy with screening questions."""
    return {
        "id": "12346",
        "name": "Senior Python Developer",
        "employer": {"name": "Tech Corp", "id": "101"},
        "description": "Senior position for experienced developers.",
        "snippet": {
            "requirement": "5+ years Python experience",
            "responsibility": "Lead development team",
        },
        "key_skills": [{"name": "Python"}, {"name": "FastAPI"}, {"name": "AWS"}],
        "archived": False,
        "relations": [],
        "questions": ["What is your expected salary?", "Can you start immediately?"],
    }


@pytest.fixture
def archived_vacancy():
    """Archived vacancy for testing filters."""
    return {
        "id": "99999",
        "name": "Old Position",
        "employer": {"name": "Old Company"},
        "archived": True,
        "description": "This position is archived",
    }


@pytest.fixture
def sample_apply_request():
    """Sample ApplyRequest for testing."""
    from app.schemas.apply import ApplyRequest

    return ApplyRequest(
        position="Python Developer",
        resume="Experienced Python developer with 5 years of experience",
        skills="Python, Django, FastAPI, PostgreSQL, Redis",
        experience="5 years in software development",
        resume_id="resume_123",
    )


@pytest.fixture
def sample_bulk_apply_request():
    """Sample BulkApplyRequest for testing."""
    from app.schemas.apply import BulkApplyRequest

    return BulkApplyRequest(
        position="Python Developer",
        resume="Experienced Python developer",
        skills="Python, Django, FastAPI",
        experience="5 years experience",
        resume_id="resume_123",
        exclude_companies=["Bad Company", "Spam Corp"],
        salary_min=100000,
        remote_only=True,
        required_skills=["Python", "Django"],
        excluded_keywords=["junior", "intern"],
        use_cover_letter=True,
    )


@pytest.fixture
def mock_hh_client():
    """Mock HH client for testing."""
    client = MagicMock()
    client.search_vacancies = AsyncMock(return_value={"items": [], "found": 0})
    client.get_vacancy_details = AsyncMock(return_value={})
    client.get_vacancy_questions = AsyncMock(return_value=[])
    client.apply = AsyncMock(return_value={"status": "success"})
    client.get_my_resumes = AsyncMock(return_value=[])
    client.get_resume_details = AsyncMock(return_value={})
    client.get_applied_vacancy_ids = AsyncMock(return_value=set())
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    provider = MagicMock()
    provider.generate_cover_letter = AsyncMock(
        return_value="Dear Hiring Manager, I am excited to apply..."
    )
    provider.answer_screening_questions = AsyncMock(
        return_value=[{"id": "1", "answer": "Test answer"}]
    )
    return provider
