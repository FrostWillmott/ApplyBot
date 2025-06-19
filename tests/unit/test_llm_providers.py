"""Unit tests for LLM providers."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm.providers import ClaudeProvider


class TestClaudeProvider:
    """Test Claude LLM provider."""

    @pytest.fixture
    def claude_provider(self):
        """Create Claude provider with mocked client."""
        with patch("app.services.llm.providers.Anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client

            # Mock response structure
            mock_response = AsyncMock()
            mock_response.content = [AsyncMock()]
            mock_response.content[0].text = "Generated text response"
            mock_client.messages.create.return_value = mock_response

            provider = ClaudeProvider("test_api_key")
            provider.client = mock_client
            return provider

    @pytest.mark.asyncio
    async def test_generate_basic(self, claude_provider):
        """Test basic text generation."""
        result = await claude_provider.generate("Test prompt")
        assert result == "Generated text response"

    @pytest.mark.asyncio
    async def test_generate_cover_letter(self, claude_provider, sample_vacancy):
        """Test cover letter generation."""
        user_profile = {
            "name": "John Doe",
            "experience": "5+ years Python development",
            "skills": "Python, FastAPI, PostgreSQL",
        }

        result = await claude_provider.generate_cover_letter(sample_vacancy, user_profile)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_answer_screening_questions(self, claude_provider, sample_vacancy):
        """Test screening questions answering."""
        questions = [
            {"id": "1", "text": "Why do you want to work here?"},
            {"id": "2", "text": "Describe your experience"},
        ]
        user_profile = {"experience": "5 years", "skills": "Python"}

        result = await claude_provider.answer_screening_questions(
            questions, sample_vacancy, user_profile
        )

        assert len(result) == 2
        assert all("id" in answer and "answer" in answer for answer in result)
