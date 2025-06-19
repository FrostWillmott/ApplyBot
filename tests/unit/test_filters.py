"""Unit tests for application filters."""

import pytest

from app.schemas.apply import BulkApplyRequest
from app.utils.filters import ApplicationFilter


class TestApplicationFilter:
    """Test application filtering logic."""

    def test_company_exclusion_filter(self):
        """Test company exclusion filtering."""
        request = BulkApplyRequest(
            position="Developer",
            resume="Resume",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
            exclude_companies=["BadCorp", "WorstCorp"],
        )
        filter_engine = ApplicationFilter(request)

        vacancy = {
            "employer": {"name": "BadCorp Inc"},
            "name": "Developer",
        }

        should_apply, reason = filter_engine.should_apply(vacancy)
        assert not should_apply
        assert "Excluded company" in reason

    def test_salary_filter(self):
        """Test salary filtering."""
        request = BulkApplyRequest(
            position="Developer",
            resume="Resume",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
            salary_min=100000,
        )
        filter_engine = ApplicationFilter(request)

        # Vacancy with low salary
        vacancy_low = {
            "employer": {"name": "TechCorp"},
            "salary": {"from": 50000, "to": 80000},
        }

        should_apply, reason = filter_engine.should_apply(vacancy_low)
        assert not should_apply
        assert "Salary below minimum" in reason

        # Vacancy with good salary
        vacancy_good = {
            "employer": {"name": "TechCorp"},
            "salary": {"from": 120000, "to": 150000},
        }

        should_apply, reason = filter_engine.should_apply(vacancy_good)
        assert should_apply

    def test_remote_filter(self):
        """Test remote work filtering."""
        request = BulkApplyRequest(
            position="Developer",
            resume="Resume",
            skills="Python",
            experience="5 years",
            resume_id="resume_123",
            remote_only=True,
        )
        filter_engine = ApplicationFilter(request)

        # Non-remote vacancy
        vacancy_office = {
            "employer": {"name": "TechCorp"},
            "schedule": {"name": "Полный день"},
        }

        should_apply, reason = filter_engine.should_apply(vacancy_office)
        assert not should_apply
        assert "Not a remote position" in reason

        # Remote vacancy
        vacancy_remote = {
            "employer": {"name": "TechCorp"},
            "schedule": {"name": "Удаленная работа"},
        }

        should_apply, reason = filter_engine.should_apply(vacancy_remote)
        assert should_apply