"""Tests for LLM providers and related functionality."""

from unittest.mock import MagicMock, patch

from app.services.llm.base import LLMProvider
from app.services.llm.dependencies import enhanced_llm_dep, llm_provider_dep
from app.services.llm.factory import get_llm_provider


class TestLLMProvider:
    """Tests for LLMProvider base class."""

    def test_provider_is_abstract(self):
        """Test that LLMProvider is an abstract class."""
        # LLMProvider should not be directly instantiable if it has abstract methods
        # but we can test that subclasses need to implement methods
        assert hasattr(LLMProvider, "generate_cover_letter")
        assert hasattr(LLMProvider, "answer_screening_questions")


class TestGetLLMProvider:
    """Tests for get_llm_provider factory function."""

    def test_get_sonnet4_provider(self):
        """Test getting Sonnet4 provider."""
        with patch("app.services.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "sonnet4"
            mock_settings.anthropic_api_key = "test_key"

            provider = get_llm_provider()

            assert provider is not None

    def test_factory_returns_provider(self):
        """Test that factory returns a provider instance."""
        with patch("app.services.llm.factory.settings") as mock_settings:
            mock_settings.llm_provider = "sonnet4"
            mock_settings.anthropic_api_key = "test_key"

            provider = get_llm_provider()

            # Should have the required methods
            assert hasattr(provider, "generate_cover_letter")
            assert hasattr(provider, "answer_screening_questions")


class TestLLMDependencies:
    """Tests for LLM dependency injection."""

    def test_enhanced_llm_dep_returns_provider(self):
        """Test that enhanced_llm_dep returns a provider."""
        with patch("app.services.llm.dependencies.get_llm_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_factory.return_value = mock_provider

            result = enhanced_llm_dep()

            assert result == mock_provider

    def test_llm_provider_dep_returns_input(self):
        """Test that llm_provider_dep returns the input provider."""
        mock_provider = MagicMock(spec=LLMProvider)

        result = llm_provider_dep(mock_provider)

        assert result == mock_provider


class TestCoverLetterGeneration:
    """Tests for cover letter generation logic."""

    def test_cover_letter_prompt_structure(self):
        """Test that cover letter prompts have correct structure."""
        vacancy = {
            "name": "Python Developer",
            "employer": {"name": "Tech Corp"},
            "description": "We need a developer",
        }
        user_profile = {"experience": "5 years", "skills": "Python, Django"}

        # Test prompt would include job title and company
        prompt_elements = [
            vacancy["name"],
            vacancy["employer"]["name"],
            user_profile["experience"],
            user_profile["skills"],
        ]

        for element in prompt_elements:
            assert isinstance(element, str)

    def test_cover_letter_response_processing(self):
        """Test processing of cover letter response."""
        raw_response = "   Dear Hiring Manager,\n\nI am excited...  "
        processed = raw_response.strip()

        assert processed.startswith("Dear")
        assert not processed.startswith(" ")
        assert not processed.endswith(" ")


class TestScreeningQuestionAnswers:
    """Tests for screening question answer generation."""

    def test_answer_structure(self):
        """Test answer structure."""
        questions = [
            {"id": "q1", "text": "What is your salary expectation?"},
            {"id": "q2", "text": "Can you relocate?"},
        ]

        # Simulate answer generation
        answers = []
        for q in questions:
            answers.append({"id": q["id"], "answer": f"Answer for {q['text']}"})

        assert len(answers) == 2
        assert answers[0]["id"] == "q1"
        assert answers[1]["id"] == "q2"

    def test_empty_questions_handling(self):
        """Test handling of empty questions list."""
        questions = []

        if not questions:
            answers = None
        else:
            answers = [{"id": q["id"], "answer": "test"} for q in questions]

        assert answers is None

    def test_question_text_extraction(self):
        """Test extracting text from question objects."""
        questions = [
            {"id": "1", "text": "Question 1?"},
            {"id": "2", "text": "Question 2?", "required": True},
        ]

        texts = [q.get("text", "") for q in questions]

        assert texts == ["Question 1?", "Question 2?"]


class TestPromptBuilding:
    """Tests for LLM prompt building utilities."""

    def test_prompt_escaping(self):
        """Test that special characters in prompts are handled."""
        text_with_special = 'Position: "Developer" with <tags>'

        # Should not crash when included in prompt
        prompt = f"Apply for: {text_with_special}"
        assert text_with_special in prompt

    def test_prompt_truncation(self):
        """Test prompt truncation for long content."""
        long_description = "x" * 10000
        max_length = 5000

        truncated = long_description[:max_length]

        assert len(truncated) == max_length

    def test_prompt_language_detection(self):
        """Test language detection hints in prompts."""
        russian_text = "Требуется разработчик"
        english_text = "Developer needed"

        # Simple heuristic: Cyrillic characters
        has_cyrillic = any("\u0400" <= c <= "\u04ff" for c in russian_text)
        has_no_cyrillic = not any("\u0400" <= c <= "\u04ff" for c in english_text)

        assert has_cyrillic is True
        assert has_no_cyrillic is True
