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

        # Experience level filter
        if self.request.experience_level:
            if not self._matches_experience_level(vacancy):
                return False, "Experience level mismatch"

        # Required skills filter
        if self.request.required_skills:
            missing_skills = self._check_required_skills(vacancy)
            if missing_skills:
                return False, f"Missing required skills: {', '.join(missing_skills)}"

        # Excluded keywords filter
        if self.request.excluded_keywords:
            found_keywords = self._check_excluded_keywords(vacancy)
            if found_keywords:
                return False, f"Found excluded keywords: {', '.join(found_keywords)}"

        # Employment type filter
        if self.request.employment_types:
            if not self._matches_employment_type(vacancy):
                return False, "Employment type mismatch"

        # Schedule preference filter
        if self.request.preferred_schedule:
            if not self._matches_preferred_schedule(vacancy):
                return False, "Schedule mismatch"

        # Commute time filter
        if self.request.max_commute_time:
            if not self._within_commute_range(vacancy):
                return False, "Commute time exceeds maximum"

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
        address = vacancy.get("address", {})

        # Check schedule name
        remote_keywords = ["удален", "remote", "дистанцион", "на дому"]
        if any(keyword in schedule for keyword in remote_keywords):
            return True

        # Check description for remote work mentions
        description = vacancy.get("description", "").lower()
        remote_desc_keywords = ["удаленная работа", "remote work", "работа из дома", "дистанционная работа"]
        if any(keyword in description for keyword in remote_desc_keywords):
            return True

        return False

    def _matches_experience_level(self, vacancy: dict) -> bool:
        """Check if experience level matches."""
        vacancy_experience = vacancy.get("experience", {}).get("id")

        if not vacancy_experience:
            return True  # No experience info, assume it might be acceptable

        # If exact match
        if vacancy_experience == self.request.experience_level:
            return True

        # Handle special cases
        if self.request.experience_level == "noExperience":
            # Only accept no experience positions
            return vacancy_experience == "noExperience"
        elif self.request.experience_level == "between1And3":
            # Accept positions requiring less experience
            return vacancy_experience in ["noExperience", "between1And3"]
        elif self.request.experience_level == "between3And6":
            # Accept positions requiring less experience
            return vacancy_experience in ["noExperience", "between1And3", "between3And6"]
        elif self.request.experience_level == "moreThan6":
            # Accept any experience level
            return True

        return False

    def _check_required_skills(self, vacancy: dict) -> list[str]:
        """Check if vacancy contains all required skills.

        Returns:
            list: Missing skills
        """
        if not self.request.required_skills:
            return []

        description = vacancy.get("description", "").lower()
        key_skills = [skill.get("name", "").lower() for skill in vacancy.get("key_skills", [])]

        missing_skills = []
        for required_skill in self.request.required_skills:
            skill_lower = required_skill.lower()
            # Check if skill is in key_skills or description
            if skill_lower not in key_skills and skill_lower not in description:
                missing_skills.append(required_skill)

        return missing_skills

    def _check_excluded_keywords(self, vacancy: dict) -> list[str]:
        """Check if vacancy contains any excluded keywords.

        Returns:
            list: Found excluded keywords
        """
        if not self.request.excluded_keywords:
            return []

        description = vacancy.get("description", "").lower()
        name = vacancy.get("name", "").lower()

        found_keywords = []
        for keyword in self.request.excluded_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in description or keyword_lower in name:
                found_keywords.append(keyword)

        return found_keywords

    def _matches_employment_type(self, vacancy: dict) -> bool:
        """Check if vacancy matches acceptable employment types."""
        if not self.request.employment_types:
            return True

        employment_type = vacancy.get("employment", {}).get("id")
        if not employment_type:
            return True  # No employment info, assume it might be acceptable

        return employment_type in self.request.employment_types

    def _matches_preferred_schedule(self, vacancy: dict) -> bool:
        """Check if vacancy matches preferred work schedule."""
        if not self.request.preferred_schedule:
            return True

        schedule = vacancy.get("schedule", {}).get("id")
        if not schedule:
            return True  # No schedule info, assume it might be acceptable

        return schedule in self.request.preferred_schedule

    def _within_commute_range(self, vacancy: dict) -> bool:
        """Check if vacancy is within acceptable commute range."""
        if not self.request.max_commute_time:
            return True

        # This is a simplified implementation
        # In a real-world scenario, you might want to use a geocoding/routing API
        # to calculate actual commute times

        # For now, we'll just check if the address exists
        address = vacancy.get("address")
        if not address:
            return True  # No address info, assume it might be acceptable

        # If we had user's location and a routing API, we could calculate actual commute time
        # For now, we'll just return True
        return True
