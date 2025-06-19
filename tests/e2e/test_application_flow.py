"""End-to-end tests for complete application flow."""

from unittest.mock import AsyncMock, patch

import pytest


class TestE2EApplicationFlow:
    """Test complete application workflow."""

    @pytest.mark.asyncio
    async def test_complete_application_workflow(
            self, test_client, db_session, mock_hh_token
    ):
        """Test complete workflow from search to application."""

        # Mock all external dependencies
        with patch("app.services.hh_client.HHClient") as mock_hh_client:
            with patch("app.services.llm.factory.get_llm_provider") as mock_llm:

                # Setup HH client mock
                mock_client = AsyncMock()
                mock_client.search_vacancies.return_value = {
                    "items": [
                        {
                            "id": "12345",
                            "name": "Python Developer",
                            "employer": {"name": "TechCorp"},
                        }
                    ]
                }
                mock_client.get_vacancy_details.return_value = {
                    "id": "12345",
                    "name": "Python Developer",
                    "employer": {"name": "TechCorp"},
                    "description": "Job description",
                }
                mock_client.apply.return_value = {"status": "ok"}
                mock_hh_client.return_value = mock_client

                # Setup LLM provider mock
                mock_provider = AsyncMock()
                mock_provider.generate_cover_letter.return_value = "Generated cover letter"
                mock_llm.return_value = mock_provider

                # Step 1: Search for vacancies
                search_response = test_client.get("/apply/search?text=Python%20Developer")
                assert search_response.status_code == 200
                vacancies = search_response.json()["items"]
                assert len(vacancies) > 0

                # Step 2: Apply to a vacancy
                application_data = {
                    "position": "Python Developer",
                    "resume": "Experienced Python developer with 5+ years...",
                    "skills": "Python, FastAPI, PostgreSQL",
                    "experience": "5+ years in web development",
                    "resume_id": "resume_123",
                }

                apply_response = test_client.post(
                    f"/apply/single/{vacancies[0]['id']}",
                    json=application_data,
                )

                assert apply_response.status_code == 200
                result = apply_response.json()
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_bulk_application_workflow(self, test_client, db_session, mock_hh_token):
        """Test bulk application workflow."""

        with patch("app.services.hh_client.HHClient") as mock_hh_client:
            with patch("app.services.llm.factory.get_llm_provider") as mock_llm:

                # Setup mocks for bulk application
                mock_client = AsyncMock()
                mock_client.search_vacancies.return_value = {
                    "items": [
                        {"id": "123", "name": "Python Dev", "employer": {"name": "Corp1"}},
                        {"id": "124", "name": "Backend Dev", "employer": {"name": "Corp2"}},
                    ]
                }
                mock_client.get_vacancy_details.side_effect = [
                    {"id": "123", "name": "Python Dev", "employer": {"name": "Corp1"}},
                    {"id": "124", "name": "Backend Dev", "employer": {"name": "Corp2"}},
                ]
                mock_client.apply.return_value = {"status": "ok"}
                mock_hh_client.return_value = mock_client

                mock_provider = AsyncMock()
                mock_provider.generate_cover_letter.return_value = "Cover letter"
                mock_llm.return_value = mock_provider

                # Bulk application request
                bulk_data = {
                    "position": "Python Developer",
                    "resume": "Experienced developer...",
                    "skills": "Python, FastAPI",
                    "experience": "5 years",
                    "resume_id": "resume_123",
                    "exclude_companies": [],
                    "salary_min": 80000,
                    "remote_only": False,
                }

                response = test_client.post(
                    "/apply/bulk?max_applications=5",
                    json=bulk_data,
                )

                assert response.status_code == 200
                results = response.json()
                assert len(results) >= 1
                assert all("status" in result for result in results)
