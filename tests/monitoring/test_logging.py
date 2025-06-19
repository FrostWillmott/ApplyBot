"""Test logging functionality."""

import logging
from unittest.mock import patch


class TestLogging:
    """Test logging functionality."""

    def test_application_logging(self, test_client, caplog):
        """Test that applications are properly logged."""
        with caplog.at_level(logging.INFO):
            with patch("app.routers.apply.get_application_service") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.apply_to_single_vacancy.return_value = AsyncMock(
                    status="success", vacancy_id="123"
                )

                application_data = {
                    "position": "Developer",
                    "resume": "Resume",
                    "skills": "Python",
                    "experience": "5 years",
                    "resume_id": "resume_123",
                }

                test_client.post(
                    "/apply/single/12345",
                    json=application_data,
                )

        # Check that relevant events were logged
        assert len(caplog.records) > 0

    def test_error_logging(self, test_client, caplog):
        """Test that errors are properly logged."""
        with caplog.at_level(logging.ERROR):
            with patch("app.routers.apply.get_application_service") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.apply_to_single_vacancy.side_effect = Exception("Test error")

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

                assert response.status_code == 500

        # Check that error was logged
        error_logs = [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert len(error_logs) > 0
