"""Application filtering logic.

Separated from service layer for reusability and testing.
"""


from app.schemas.apply import BulkApplyRequest


class ApplicationFilter:
    """Handles filtering logic for job applications."""

    def __init__(self, request: BulkApplyRequest):
        self.request = request

    def should_apply(self, vacancy: dict) -> tuple[bool, str]:
        """Determine if we should apply to this vacancy.

        Returns:
            tuple: (should_apply: bool, reason: str)
        """
        # Company exclusion filter
        if self.request.exclude_companies:
            employer_name = vacancy.get("employer", {}).get("name", "").lower()
            for excluded in self.request.exclude_companies:
                if excluded.lower() in employer_name:
                    return False, f"Excluded company: {employer_name}"

        # Salary filter
        if self.request.salary_min:
            if not self._meets_salary_requirement(vacancy):
                return False, "Salary below minimum requirement"

        # Remote work filter
        if self.request.remote_only:
            if not self._is_remote_position(vacancy):
                return False, "Not a remote position"

        # Experience level filter (if implemented)
        if hasattr(self.request, "experience_level"):
            if not self._matches_experience_level(vacancy):
                return False, "Experience level mismatch"

        return True, "Passed all filters"

    def _meets_salary_requirement(self, vacancy: dict) -> bool:
        """Check if vacancy meets salary requirements."""
        salary = vacancy.get("salary")
        if not salary:
            return True  # No salary info, assume it might be acceptable

        salary_from = salary.get("from")
        if salary_from and salary_from >= self.request.salary_min:
            return True

        return False

    def _is_remote_position(self, vacancy: dict) -> bool:
        """Check if position is remote."""
        schedule = vacancy.get("schedule", {}).get("name", "").lower()
        remote_keywords = ["удален", "remote", "дистанцион", "на дому"]
        return any(keyword in schedule for keyword in remote_keywords)

    def _matches_experience_level(self, vacancy: dict) -> bool:
        """Check if experience level matches."""
        # Implementation based on your requirements
        return True
