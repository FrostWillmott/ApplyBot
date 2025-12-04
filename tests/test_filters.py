"""Tests for application filtering logic."""

from app.schemas.apply import BulkApplyRequest
from app.utils.filters import ApplicationFilter


class TestApplicationFilter:
    """Tests for ApplicationFilter class."""

    def test_filter_init(self, sample_bulk_apply_request):
        """Test filter initialization."""
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        assert filter_engine.request == sample_bulk_apply_request

    def test_should_apply_passes_valid_vacancy(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that valid vacancy passes all filters."""
        # Modify vacancy to match required skills
        sample_vacancy["key_skills"] = [
            {"name": "Python"},
            {"name": "Django"},
            {"name": "FastAPI"},
        ]
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is True
        assert reason == "Passed all filters"

    def test_should_apply_filters_archived_vacancy(
        self, sample_bulk_apply_request, archived_vacancy
    ):
        """Test that archived vacancies are filtered out."""
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(archived_vacancy)
        assert should_apply is False
        assert "archived" in reason.lower()

    def test_should_apply_filters_excluded_company(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that excluded companies are filtered out."""
        sample_vacancy["employer"]["name"] = "Bad Company Inc"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is False
        assert "excluded company" in reason.lower()

    def test_should_apply_filters_excluded_company_case_insensitive(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that company exclusion is case insensitive."""
        sample_vacancy["employer"]["name"] = "BAD COMPANY"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is False
        assert "excluded company" in reason.lower()

    def test_should_apply_filters_missing_required_skills(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that vacancies missing required skills are filtered."""
        sample_vacancy["key_skills"] = [{"name": "Java"}]
        sample_vacancy["description"] = "Java developer position"
        sample_vacancy["name"] = "Java Developer"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is False
        assert "missing required skills" in reason.lower()

    def test_should_apply_finds_skills_in_description(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that skills found in description pass the filter."""
        sample_vacancy["key_skills"] = []
        sample_vacancy["description"] = "We need a Python and Django developer"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is True

    def test_should_apply_finds_skills_in_name(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that skills found in job title pass the filter."""
        sample_vacancy["key_skills"] = []
        sample_vacancy["description"] = ""
        sample_vacancy["name"] = "Python Django Developer"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is True

    def test_should_apply_filters_excluded_keywords(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that vacancies with excluded keywords are filtered."""
        sample_vacancy["key_skills"] = [{"name": "Python"}, {"name": "Django"}]
        sample_vacancy["description"] = "Junior Python Developer position"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is False
        assert "excluded keywords" in reason.lower()

    def test_should_apply_filters_excluded_keywords_in_name(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test that excluded keywords in job title are detected."""
        sample_vacancy["key_skills"] = [{"name": "Python"}, {"name": "Django"}]
        sample_vacancy["name"] = "Python Intern"
        sample_vacancy["description"] = "Great opportunity for beginners"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is False
        assert "excluded keywords" in reason.lower()

    def test_check_required_skills_returns_empty_when_no_skills_required(
        self, sample_vacancy
    ):
        """Test that no skills are reported missing when none required."""
        request = BulkApplyRequest(
            position="Developer", resume_id="123", required_skills=None
        )
        filter_engine = ApplicationFilter(request)
        missing = filter_engine._check_required_skills(sample_vacancy)
        assert missing == []

    def test_check_excluded_keywords_returns_empty_when_no_keywords(
        self, sample_vacancy
    ):
        """Test that no keywords are found when none specified."""
        request = BulkApplyRequest(
            position="Developer", resume_id="123", excluded_keywords=None
        )
        filter_engine = ApplicationFilter(request)
        found = filter_engine._check_excluded_keywords(sample_vacancy)
        assert found == []

    def test_should_apply_with_minimal_request(self, sample_vacancy):
        """Test filtering with minimal request (no optional filters)."""
        request = BulkApplyRequest(position="Developer", resume_id="123")
        filter_engine = ApplicationFilter(request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is True
        assert reason == "Passed all filters"

    def test_should_apply_handles_missing_employer(self, sample_bulk_apply_request):
        """Test handling vacancy without employer info."""
        vacancy = {
            "id": "123",
            "name": "Test",
            "archived": False,
            "description": "Python Django position",
            "key_skills": [{"name": "Python"}, {"name": "Django"}],
        }
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(vacancy)
        assert should_apply is True

    def test_should_apply_handles_empty_key_skills(
        self, sample_bulk_apply_request, sample_vacancy
    ):
        """Test handling vacancy with empty key_skills list."""
        sample_vacancy["key_skills"] = []
        sample_vacancy["description"] = "Python and Django developer needed"
        filter_engine = ApplicationFilter(sample_bulk_apply_request)
        should_apply, reason = filter_engine.should_apply(sample_vacancy)
        assert should_apply is True
