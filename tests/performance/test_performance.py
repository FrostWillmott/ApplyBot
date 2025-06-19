"""Performance tests for the application."""

import asyncio
import time
from unittest.mock import patch

import pytest


class TestPerformance:
    """Test application performance characteristics."""

    @pytest.mark.asyncio
    async def test_concurrent_applications(self, mock_hh_client, mock_llm_provider):
        """Test handling concurrent applications."""
        from app.schemas.apply import ApplyRequest
        from app.services.application_service import ApplicationService

        service = ApplicationService(mock_hh_client, mock_llm_provider)

        # Mock successful responses
        mock_hh_client.get_vacancy_details.return_value = {
            "id": "123", "name": "Developer", "employer": {"name": "Corp"}
        }
        mock_llm_provider.generate_cover_letter.return_value = "Cover letter"
        mock_hh_client.apply.return_value = {"status": "ok"}

        request = ApplyRequest(
            position="Developer",
            resume="Resume content",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
        )

        with patch.object(service, "_has_already_applied", return_value=False):
            with patch.object(service, "_can_apply_to_vacancy", return_value=(True, "")):

                # Run 10 concurrent applications
                start_time = time.time()
                tasks = [
                    service.apply_to_single_vacancy(f"vacancy_{i}", request)
                    for i in range(10)
                ]
                results = await asyncio.gather(*tasks)
                end_time = time.time()

                # All should succeed
                assert len(results) == 10
                assert all(result.status == "success" for result in results)

                # Should complete reasonably quickly (concurrent, not sequential)
                assert end_time - start_time < 5.0  # Should be much faster than sequential

    @pytest.mark.asyncio
    async def test_large_bulk_application(self, mock_hh_client, mock_llm_provider):
        """Test performance with large bulk applications."""
        from app.services.application_service import ApplicationService

        service = ApplicationService(mock_hh_client, mock_llm_provider)

        # Generate large list of mock vacancies
        mock_vacancies = [
            {"id": f"vac_{i}", "name": f"Job {i}", "employer": {"name": f"Corp {i}"}}
            for i in range(100)
        ]

        mock_hh_client
