"""Test error handling scenarios."""

from unittest.mock import AsyncMock, patch

from fastapi import HTTPException


class TestErrorHandling:
    """Test various error scenarios and their handling."""

    def test_hh_api_error_handling(self, test_client):
        """Test handling of HH API errors."""
        with patch("app.routers.apply.get_application_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.apply_to_single_vacancy.side_effect = HTTPException(
                status_code=502, detail="HH API unavailable"
            )

            application_data = {
                "position": "Developer",
                "resume": "Resume",
                "skills": "Python",
                "experience": "5 years",
                "resume_id": "resume_123",
            }

            response = test_client.post(
                "/apply/single/12345",
                json=application_data,
            )

            assert response.status_code == 502
            assert "HH API unavailable" in response.json()["detail"]

    def test_llm_provider_error_handling(self, test_client):
        """Test handling of LLM provider errors."""
        with patch("app.services.llm.factory.get_llm_provider") as mock_llm:
            mock_provider = AsyncMock()
            mock_provider.generate_cover_letter.side_effect = Exception("LLM service error")
            mock_llm.return_value = mock_provider

            with patch("app.routers.apply.get_application_service") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.apply_to_single_vacancy.side_effect = HTTPException(
                    status_code=503, detail="AI service temporarily unavailable"
                )

                application_data = {
                    "position": "Developer",
                    "resume": "Resume",
                    "skills": "Python",
                    "experience": "5 years",
                    "resume_id": "resume_123",
                }

                response = test_client.post(
                    "/apply/single/12345",
                    json=application_data,
                )

                assert response.status_code == 503

    def test_database_error_handling(self, test_client):
        """Test handling of database connectivity issues."""
        with patch("app.core.storage.TokenStorage.get_latest") as mock_storage:
            mock_storage.side_effect = Exception("Database connection failed")

            response = test_client.get("/apply/search?text=developer")

            # Should handle database errors gracefully
            assert response.status_code in [500, 503]

    def test_validation_error_handling(self, test_client):
        """Test handling of input validation errors."""
        invalid_data = {
            "position": "",  # Empty required field
            "resume": "Resume",
            "skills": "Python",
            "experience": "5 years",
            # Missing resume_id
        }

        response = test_client.post(
            "/apply/single/12345",
            json=invalid_data,
        )

        assert response.status_code == 422  # Validation error
        error_detail = response.json()
        assert "detail" in error_detail

    def test_timeout_handling(self, test_client):
        """Test handling of request timeouts."""
        with patch("app.services.hh_client.HHClient._make_request") as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Request timeout")

            response = test_client.get("/apply/search?text=developer")

            # Should handle timeouts gracefully
            assert response.status_code in [408, 500, 503]
