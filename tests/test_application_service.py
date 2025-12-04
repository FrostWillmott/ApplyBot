"""Tests for ApplicationService."""

from unittest.mock import AsyncMock

import pytest

from app.schemas.apply import ApplyResponse
from app.services.application_service import ApplicationService


class TestApplicationServiceInit:
    """Tests for ApplicationService initialization."""

    def test_service_init(self, mock_hh_client, mock_llm_provider):
        """Test service initialization."""
        service = ApplicationService(mock_hh_client, mock_llm_provider)
        assert service.hh_client == mock_hh_client
        assert service.llm_provider == mock_llm_provider


class TestCanApplyToVacancy:
    """Tests for _can_apply_to_vacancy method."""

    @pytest.fixture
    def service(self, mock_hh_client, mock_llm_provider):
        """Create ApplicationService instance."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.mark.asyncio
    async def test_can_apply_to_regular_vacancy(self, service, sample_vacancy):
        """Test that regular vacancy can be applied to."""
        can_apply, reason = await service._can_apply_to_vacancy(sample_vacancy)
        assert can_apply is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_cannot_apply_to_archived_vacancy(self, service, archived_vacancy):
        """Test that archived vacancy cannot be applied to."""
        can_apply, reason = await service._can_apply_to_vacancy(archived_vacancy)
        assert can_apply is False
        assert "archived" in reason.lower()

    @pytest.mark.asyncio
    async def test_cannot_apply_to_already_applied(self, service, sample_vacancy):
        """Test vacancy with existing response."""
        sample_vacancy["relations"] = ["got_response"]
        can_apply, reason = await service._can_apply_to_vacancy(sample_vacancy)
        assert can_apply is False
        assert "already applied" in reason.lower()

    @pytest.mark.asyncio
    async def test_cannot_apply_with_response_relation(self, service, sample_vacancy):
        """Test vacancy with response relation."""
        sample_vacancy["relations"] = ["response"]
        can_apply, reason = await service._can_apply_to_vacancy(sample_vacancy)
        assert can_apply is False
        assert "already applied" in reason.lower()


class TestBuildUserProfile:
    """Tests for _build_user_profile method."""

    @pytest.fixture
    def service(self, mock_hh_client, mock_llm_provider):
        """Create ApplicationService instance."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.mark.asyncio
    async def test_build_profile_with_resume_data(self, service, sample_apply_request):
        """Test building user profile from resume data."""
        resume_data = {
            "experience": [
                {
                    "company": "Tech Corp",
                    "position": "Developer",
                    "start": "2020-01",
                    "end": "2023-01",
                    "description": "Developed software",
                }
            ],
            "skill_set": ["Python", "Django", "FastAPI"],
            "education": {"items": []},
            "description": "Experienced developer",
            "title": "Senior Python Developer",
        }
        service.hh_client.get_resume_details = AsyncMock(return_value=resume_data)

        profile = await service._build_user_profile(sample_apply_request)

        assert "experience" in profile
        assert "skills" in profile
        assert "Python" in profile["skills"]

    @pytest.mark.asyncio
    async def test_build_profile_with_dict_skills(self, service, sample_apply_request):
        """Test building profile when skills are dicts."""
        resume_data = {
            "experience": [],
            "skill_set": [{"name": "Python"}, {"name": "Django"}],
            "education": {"items": []},
            "description": "",
            "title": "",
        }
        service.hh_client.get_resume_details = AsyncMock(return_value=resume_data)

        profile = await service._build_user_profile(sample_apply_request)

        assert "Python" in profile["skills"]
        assert "Django" in profile["skills"]

    @pytest.mark.asyncio
    async def test_build_profile_fallback_to_request(
        self, service, sample_apply_request
    ):
        """Test profile fallback to request data."""
        resume_data = {
            "experience": [],
            "skill_set": [],
            "education": {"items": []},
            "description": "",
            "title": "",
        }
        service.hh_client.get_resume_details = AsyncMock(return_value=resume_data)

        profile = await service._build_user_profile(sample_apply_request)

        # Should fall back to request data
        assert profile["skills"] == sample_apply_request.skills


class TestGenerateApplicationContent:
    """Tests for _generate_application_content method."""

    @pytest.fixture
    def service(self, mock_hh_client, mock_llm_provider):
        """Create ApplicationService instance."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.mark.asyncio
    async def test_generate_content_with_cover_letter(
        self, service, sample_vacancy, sample_apply_request
    ):
        """Test generating content with cover letter enabled."""
        service.hh_client.get_resume_details = AsyncMock(
            return_value={
                "experience": [],
                "skill_set": [],
                "education": {"items": []},
                "description": "",
                "title": "",
            }
        )
        service.hh_client.get_vacancy_questions = AsyncMock(return_value=[])

        result = await service._generate_application_content(
            sample_vacancy, sample_apply_request, use_cover_letter=True
        )

        assert "cover_letter" in result
        assert result["cover_letter"] is not None

    @pytest.mark.asyncio
    async def test_generate_content_without_cover_letter(
        self, service, sample_vacancy, sample_apply_request
    ):
        """Test generating content without cover letter."""
        result = await service._generate_application_content(
            sample_vacancy, sample_apply_request, use_cover_letter=False
        )

        assert result["cover_letter"] is None

    @pytest.mark.asyncio
    async def test_generate_content_with_questions(
        self, service, sample_vacancy_with_questions, sample_apply_request
    ):
        """Test generating content with screening questions."""
        service.hh_client.get_resume_details = AsyncMock(
            return_value={
                "experience": [],
                "skill_set": [],
                "education": {"items": []},
                "description": "",
                "title": "",
            }
        )
        questions = [{"id": "1", "text": "Question?"}]
        service.hh_client.get_vacancy_questions = AsyncMock(return_value=questions)

        result = await service._generate_application_content(
            sample_vacancy_with_questions, sample_apply_request, use_cover_letter=True
        )

        assert "answers" in result


class TestSearchVacanciesForBulk:
    """Tests for _search_vacancies_for_bulk method."""

    @pytest.fixture
    def service(self, mock_hh_client, mock_llm_provider):
        """Create ApplicationService instance."""
        return ApplicationService(mock_hh_client, mock_llm_provider)

    @pytest.mark.asyncio
    async def test_search_with_remote_only(self, service, sample_bulk_apply_request):
        """Test search with remote_only filter."""
        sample_bulk_apply_request.remote_only = True
        service.hh_client.search_vacancies = AsyncMock(
            return_value={"items": [{"id": "1", "name": "Remote Job"}], "found": 1}
        )

        vacancies = await service._search_vacancies_for_bulk(
            sample_bulk_apply_request, max_applications=10
        )

        # Verify search was called with schedule="remote"
        call_kwargs = service.hh_client.search_vacancies.call_args.kwargs
        assert call_kwargs.get("schedule") == "remote"

    @pytest.mark.asyncio
    async def test_search_collects_multiple_pages(
        self, service, sample_bulk_apply_request
    ):
        """Test that search collects vacancies from multiple pages."""
        # First page returns items, second page returns empty
        service.hh_client.search_vacancies = AsyncMock(
            side_effect=[
                {"items": [{"id": str(i)} for i in range(100)], "found": 150},
                {"items": [{"id": str(i)} for i in range(100, 150)], "found": 150},
                {"items": [], "found": 150},
            ]
        )

        vacancies = await service._search_vacancies_for_bulk(
            sample_bulk_apply_request, max_applications=10
        )

        assert len(vacancies) > 0


class TestApplyResponse:
    """Tests for ApplyResponse creation in various scenarios."""

    def test_success_response(self):
        """Test creating success response."""
        response = ApplyResponse(
            vacancy_id="123",
            status="success",
            vacancy_title="Developer",
            cover_letter="Cover letter text",
        )
        assert response.status == "success"
        assert response.error_detail is None

    def test_error_response(self):
        """Test creating error response."""
        response = ApplyResponse(
            vacancy_id="123", status="error", error_detail="Application failed"
        )
        assert response.status == "error"
        assert response.error_detail == "Application failed"

    def test_skipped_response(self):
        """Test creating skipped response."""
        response = ApplyResponse(
            vacancy_id="123",
            status="skipped",
            vacancy_title="Old Job",
            error_detail="Already applied (HH.ru)",
        )
        assert response.status == "skipped"
        assert "already" in response.error_detail.lower()
