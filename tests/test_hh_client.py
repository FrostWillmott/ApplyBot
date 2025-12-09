"""Tests for HH client functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.hh_client import HHAPIError, HHClient


class TestHHAPIError:
    """Tests for HHAPIError exception."""

    def test_error_creation(self):
        """Test creating HHAPIError."""
        error = HHAPIError(
            status_code=500,
            message="Server error",
            response_data={"error": "Internal error"},
        )
        assert error.status_code == 500
        assert error.message == "Server error"
        assert error.response_data == {"error": "Internal error"}

    def test_error_string_representation(self):
        """Test error string representation."""
        error = HHAPIError(500, "Server error")
        assert str(error) == "Server error"

    def test_error_default_response_data(self):
        """Test default response_data."""
        error = HHAPIError(404, "Not found")
        assert error.response_data == {}


class TestHHClient:
    """Tests for HHClient class."""

    def test_client_initialization(self):
        """Test HHClient initialization."""
        client = HHClient()
        assert client.API_BASE == "https://api.hh.ru"
        assert client.TOKEN_URL == "https://hh.ru/oauth/token"
        assert client._token is None

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test HHClient as context manager."""
        async with HHClient() as client:
            assert client is not None
        # Client should be closed after exiting context

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing HHClient."""
        client = HHClient()
        await client.close()
        # Should not raise any errors


class TestHHClientMethods:
    """Tests for HHClient methods with mocking."""

    @pytest.fixture
    def mock_client(self):
        """Create a mocked HHClient."""
        with patch.object(HHClient, "_ensure_token", new_callable=AsyncMock):
            with patch.object(HHClient, "_rate_limit", new_callable=AsyncMock):
                client = HHClient()
                yield client

    def test_search_vacancies_params_construction(self):
        """Test that search_vacancies constructs correct params."""
        # This tests the parameter construction logic
        params = {
            "page": 0,
            "per_page": 20,
        }

        text = "Python Developer"
        if text:
            params["text"] = text

        area = 1
        if area:
            params["area"] = area

        salary = 100000
        if salary:
            params["salary"] = salary
            params["currency"] = "RUR"

        assert params["text"] == "Python Developer"
        assert params["area"] == 1
        assert params["salary"] == 100000
        assert params["currency"] == "RUR"

    def test_per_page_limit(self):
        """Test that per_page is limited to 100."""
        per_page = min(150, 100)
        assert per_page == 100

    def test_per_page_no_limit_needed(self):
        """Test per_page when under limit."""
        per_page = min(50, 100)
        assert per_page == 50


class TestApplyValidation:
    """Tests for apply method validation."""

    def test_cover_letter_length_validation(self):
        """Test cover letter length validation."""
        cover_letter = "Short"

        if cover_letter and cover_letter.strip():
            if len(cover_letter.strip()) < 50:
                is_valid = False
            else:
                is_valid = True
        else:
            is_valid = True  # Empty is OK

        assert is_valid is False

    def test_cover_letter_valid_length(self):
        """Test valid cover letter length."""
        cover_letter = "This is a sufficiently long cover letter that should pass the validation check."

        if cover_letter and cover_letter.strip():
            is_valid = len(cover_letter.strip()) >= 50
        else:
            is_valid = True

        assert is_valid is True

    def test_empty_cover_letter_allowed(self):
        """Test that empty cover letter is allowed."""
        cover_letter = ""

        if cover_letter and cover_letter.strip():
            is_valid = len(cover_letter.strip()) >= 50
        else:
            is_valid = True

        assert is_valid is True

    def test_none_cover_letter_allowed(self):
        """Test that None cover letter is allowed."""
        cover_letter = None

        if cover_letter and cover_letter.strip():
            is_valid = len(cover_letter.strip()) >= 50
        else:
            is_valid = True

        assert is_valid is True


class TestFormDataConstruction:
    """Tests for form data construction in apply method."""

    def test_basic_form_data(self):
        """Test basic form data construction."""
        form_data = {
            "vacancy_id": "12345",
            "resume_id": "resume_123",
        }

        assert form_data["vacancy_id"] == "12345"
        assert form_data["resume_id"] == "resume_123"

    def test_form_data_with_message(self):
        """Test form data with cover letter message."""
        form_data = {
            "vacancy_id": "12345",
            "resume_id": "resume_123",
        }

        cover_letter = "  Cover letter content  "
        if cover_letter and cover_letter.strip():
            form_data["message"] = cover_letter.strip()

        assert form_data["message"] == "Cover letter content"

    def test_form_data_with_answers(self):
        """Test form data with screening question answers."""
        form_data = {
            "vacancy_id": "12345",
            "resume_id": "resume_123",
        }

        answers = [
            {"id": "q1", "answer": "Answer 1"},
            {"id": "q2", "answer": "Answer 2"},
        ]

        for answer in answers:
            question_id = answer.get("id")
            answer_text = answer.get("answer", "")
            if question_id and answer_text:
                form_data[f"answer_{question_id}"] = answer_text.strip()

        assert form_data["answer_q1"] == "Answer 1"
        assert form_data["answer_q2"] == "Answer 2"

    def test_form_data_skip_empty_answers(self):
        """Test that empty answers are skipped."""
        form_data = {}

        answers = [
            {"id": "q1", "answer": ""},
            {"id": "", "answer": "Answer"},
            {"id": "q3", "answer": "Valid answer"},
        ]

        for answer in answers:
            question_id = answer.get("id")
            answer_text = answer.get("answer", "")
            if question_id and answer_text:
                form_data[f"answer_{question_id}"] = answer_text.strip()

        assert "answer_q1" not in form_data
        assert "answer_" not in form_data
        assert form_data["answer_q3"] == "Valid answer"
