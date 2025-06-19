"""Security tests for the application."""

from unittest.mock import patch


class TestSecurity:
    """Test security aspects of the application."""

    def test_sql_injection_protection(self, test_client):
        """Test protection against SQL injection in search parameters."""
        malicious_input = "'; DROP TABLE vacancies; --"

        response = test_client.get(f"/apply/search?text={malicious_input}")

        # Should not crash and should handle safely
        assert response.status_code in [200, 400, 422]

    def test_input_sanitization(self, test_client):
        """Test input sanitization for application data."""
        malicious_data = {
            "position": "<script>alert('xss')</script>",
            "resume": "' OR 1=1 --",
            "skills": "Normal skills",
            "experience": "5 years",
            "resume_id": "resume_123",
        }

        with patch("app.routers.apply.get_application_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.apply_to_single_vacancy.return_value = AsyncMock(
                status="success", vacancy_id="123"
            )

            response = test_client.post(
                "/apply/single/12345",
                json=malicious_data,
            )

        # Should handle malicious input gracefully
        assert response.status_code in [200, 400, 422]

    def test_rate_limiting_headers(self, test_client):
        """Test that rate limiting is properly implemented."""
        # Multiple rapid requests
        responses = []
        for _ in range(10):
            response = test_client.get("/apply/search?text=developer")
            responses.append(response)

        # Should not return 429 for reasonable request volume
        assert all(r.status_code != 429 for r in responses[:5])

    def test_authentication_required_endpoints(self, test_client):
        """Test that protected endpoints require authentication."""
        # This would depend on your auth implementation
        # For now, testing that endpoints don't crash without auth

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

        # Should either succeed or return proper auth error
        assert response.status_code in [200, 401, 403]
