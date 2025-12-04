"""Tests for prompt builder functionality."""

from app.schemas.apply import ApplyRequest
from app.services.prompt_builder import build_application_prompt


class TestBuildApplicationPrompt:
    """Tests for build_application_prompt function."""

    def test_basic_prompt_generation(self, sample_apply_request, sample_vacancy):
        """Test basic prompt generation."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Python Developer" in prompt
        assert "Test Company" in prompt

    def test_prompt_contains_job_details(self, sample_apply_request, sample_vacancy):
        """Test that prompt contains job details."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        # Should contain vacancy title and company
        assert sample_vacancy["name"] in prompt
        assert sample_vacancy["employer"]["name"] in prompt

    def test_prompt_contains_requirements(self, sample_apply_request, sample_vacancy):
        """Test that prompt contains job requirements."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        # Should contain requirements from snippet
        assert sample_vacancy["snippet"]["requirement"] in prompt

    def test_prompt_contains_responsibilities(
        self, sample_apply_request, sample_vacancy
    ):
        """Test that prompt contains job responsibilities."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert sample_vacancy["snippet"]["responsibility"] in prompt

    def test_prompt_contains_applicant_info(self, sample_apply_request, sample_vacancy):
        """Test that prompt contains applicant information."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert sample_apply_request.resume in prompt
        assert sample_apply_request.skills in prompt
        assert sample_apply_request.experience in prompt

    def test_prompt_contains_key_skills(self, sample_apply_request, sample_vacancy):
        """Test that prompt contains key skills from vacancy."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        # Key skills should be formatted as comma-separated
        assert "Python" in prompt
        assert "Django" in prompt

    def test_prompt_with_questions(
        self, sample_apply_request, sample_vacancy_with_questions
    ):
        """Test prompt generation with screening questions."""
        prompt = build_application_prompt(
            sample_apply_request, sample_vacancy_with_questions
        )

        assert "Screening Answers" in prompt
        assert "What is your expected salary?" in prompt
        assert "Can you start immediately?" in prompt

    def test_prompt_without_questions(self, sample_apply_request, sample_vacancy):
        """Test prompt generation without screening questions."""
        sample_vacancy["questions"] = []
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert "Screening Answers" not in prompt

    def test_prompt_with_empty_snippet(self, sample_apply_request):
        """Test prompt with missing snippet data."""
        vacancy = {
            "id": "123",
            "name": "Developer",
            "employer": {"name": "Company"},
            "description": "Job description",
            "snippet": {},
            "key_skills": [],
            "questions": [],
        }
        prompt = build_application_prompt(sample_apply_request, vacancy)

        assert isinstance(prompt, str)
        assert "Developer" in prompt

    def test_prompt_with_missing_employer(self, sample_apply_request):
        """Test prompt with missing employer data."""
        vacancy = {
            "id": "123",
            "name": "Developer",
            "employer": {},
            "description": "Job description",
            "snippet": {"requirement": "", "responsibility": ""},
            "key_skills": [],
            "questions": [],
        }
        prompt = build_application_prompt(sample_apply_request, vacancy)

        # Should handle missing employer gracefully
        assert "Unknown Employer" in prompt

    def test_prompt_with_missing_name(self, sample_apply_request):
        """Test prompt with missing vacancy name."""
        vacancy = {
            "id": "123",
            "employer": {"name": "Company"},
            "description": "Job description",
            "snippet": {"requirement": "", "responsibility": ""},
            "key_skills": [],
            "questions": [],
        }
        prompt = build_application_prompt(sample_apply_request, vacancy)

        assert "Unknown Position" in prompt

    def test_prompt_contains_full_description(
        self, sample_apply_request, sample_vacancy
    ):
        """Test that prompt contains full job description."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        assert sample_vacancy["description"] in prompt

    def test_prompt_is_well_structured(self, sample_apply_request, sample_vacancy):
        """Test that prompt has proper structure."""
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        # Should mention it's for a cover letter
        assert "cover letter" in prompt.lower()
        # Should have professional context
        assert "career coach" in prompt.lower()

    def test_prompt_with_empty_key_skills(self, sample_apply_request, sample_vacancy):
        """Test prompt with empty key_skills list."""
        sample_vacancy["key_skills"] = []
        prompt = build_application_prompt(sample_apply_request, sample_vacancy)

        # Should handle empty key skills gracefully
        assert isinstance(prompt, str)

    def test_prompt_with_none_resume(self, sample_vacancy):
        """Test prompt when resume is None."""
        request = ApplyRequest(
            resume=None, skills="Python", experience="5 years", resume_id="123"
        )
        prompt = build_application_prompt(request, sample_vacancy)

        # Should handle None values
        assert isinstance(prompt, str)

    def test_prompt_with_multiple_questions(self, sample_apply_request):
        """Test prompt with multiple screening questions."""
        vacancy = {
            "id": "123",
            "name": "Developer",
            "employer": {"name": "Company"},
            "description": "Description",
            "snippet": {"requirement": "", "responsibility": ""},
            "key_skills": [],
            "questions": [
                "Question 1?",
                "Question 2?",
                "Question 3?",
                "Question 4?",
                "Question 5?",
            ],
        }
        prompt = build_application_prompt(sample_apply_request, vacancy)

        # All questions should be numbered
        assert "1. Question 1?" in prompt
        assert "2. Question 2?" in prompt
        assert "5. Question 5?" in prompt

    def test_prompt_preserves_question_order(self, sample_apply_request):
        """Test that questions maintain their order."""
        vacancy = {
            "id": "123",
            "name": "Developer",
            "employer": {"name": "Company"},
            "description": "Description",
            "snippet": {"requirement": "", "responsibility": ""},
            "key_skills": [],
            "questions": ["First", "Second", "Third"],
        }
        prompt = build_application_prompt(sample_apply_request, vacancy)

        first_pos = prompt.find("First")
        second_pos = prompt.find("Second")
        third_pos = prompt.find("Third")

        assert first_pos < second_pos < third_pos
