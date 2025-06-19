"""Unit tests for prompt building."""

import pytest

from app.schemas.apply import ApplyRequest
from app.services.prompt_builder import build_application_prompt


class TestPromptBuilder:
    """Test prompt building functionality."""

    def test_basic_prompt_building(self, sample_apply_request, sample_vacancy):
        """Test basic prompt construction."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert "Python Developer" in prompt
        assert "Tech Corp" in prompt
        assert sample_apply_request.resume in prompt
        assert sample_apply_request.skills in prompt

    def test_prompt_with_questions(self, sample_apply_request):
        """Test prompt building with screening questions."""
        vacancy = {
            "name": "Developer",
            "employer": {"name": "TechCorp"},
            "snippet": {"requirement": "Python", "responsibility": "Code"},
            "description": "Job description",
            "key_skills": [{"name": "Python"}],
            "questions": ["Why do you want this job?", "Describe your experience"],
        }

        prompt = build_application_prompt(sample_apply_request, vacancy)

        assert "Screening Answers" in prompt
        assert "Why do you want this job?" in prompt
        assert "Describe your experience" in prompt