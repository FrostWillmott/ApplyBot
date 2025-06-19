"""Test data integrity and validation."""

from datetime import datetime, timedelta

import pytest

from app.core.storage import Token
from app.schemas.apply import ApplyRequest, BulkApplyRequest


class TestDataIntegrity:
    """Test data validation and integrity."""

    def test_token_expiration_logic(self):
        """Test token expiration logic."""
        # Valid token
        valid_token = Token(
            access_token="token",
            refresh_token="refresh",
            expires_in=3600,
            obtained_at=datetime.utcnow() - timedelta(minutes=30)
        )
        assert not valid_token.is_expired()

        # Expired token
        expired_token = Token(
            access_token="token",
            refresh_token="refresh",
            expires_in=3600,
            obtained_at=datetime.utcnow() - timedelta(hours=2)
        )
        assert expired_token.is_expired()

    def test_application_request_validation(self):
        """Test application request data validation."""
        # Valid request
        valid_request = ApplyRequest(
            position="Python Developer",
            resume="Detailed resume content with sufficient length",
            skills="Python, FastAPI, PostgreSQL, Docker",
            experience="5+ years in web development",
            resume_id="resume_123",
        )
        assert valid_request.position == "Python Developer"
        assert len(valid_request.resume) > 10

        # Test field requirements
        with pytest.raises(ValueError):
            ApplyRequest(
                position="",  # Empty position
                resume="Resume",
                skills="Skills",
                experience="Experience",
                resume_id="resume_123",
            )

    def test_bulk_request_validation(self):
        """Test bulk application request validation."""
        valid_bulk = BulkApplyRequest(
            position="Developer",
            resume="Resume content",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
            exclude_companies=["BadCorp"],
            salary_min=80000,
            remote_only=True,
        )

        assert valid_bulk.exclude_companies == ["BadCorp"]
        assert valid_bulk.salary_min == 80000
        assert valid_bulk.remote_only is True

    def test_vacancy_data_integrity(self, sample_vacancy):
        """Test vacancy data structure integrity."""
        required_fields = ["id", "name", "employer"]
        for field in required_fields:
            assert field in sample_vacancy

        # Test employer structure
        assert "name" in sample_vacancy["employer"]

        # Test optional fields handling
        snippet = sample_vacancy.get("snippet", {})
        assert isinstance(snippet, dict)
