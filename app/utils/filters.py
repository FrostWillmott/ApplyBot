"""Application filtering logic."""

from app.schemas.apply import BulkApplyRequest


class ApplicationFilter:
    """Filters for criteria not supported by HH.ru API."""

    def __init__(self, request: BulkApplyRequest):
        self.request = request

    def should_apply(self, vacancy: dict) -> tuple[bool, str]:
        """Determine if we should apply to this vacancy."""
        if vacancy.get("archived", False):
            return False, "Vacancy is archived"

        if self.request.exclude_companies:
            employer_name = vacancy.get("employer", {}).get("name", "").lower()
            for excluded in self.request.exclude_companies:
                if excluded.lower() in employer_name:
                    return False, f"Excluded company: {employer_name}"

        if self.request.required_skills:
            missing_skills = self._check_required_skills(vacancy)
            if missing_skills:
                return False, f"Missing required skills: {', '.join(missing_skills)}"

        if self.request.excluded_keywords:
            found_keywords = self._check_excluded_keywords(vacancy)
            if found_keywords:
                return False, f"Found excluded keywords: {', '.join(found_keywords)}"

        return True, "Passed all filters"

    def _check_required_skills(self, vacancy: dict) -> list[str]:
        """Check if vacancy contains all required skills."""
        if not self.request.required_skills:
            return []

        description = vacancy.get("description", "").lower()
        name = vacancy.get("name", "").lower()
        key_skills = [
            skill.get("name", "").lower() for skill in vacancy.get("key_skills", [])
        ]

        missing = []
        for skill in self.request.required_skills:
            skill_lower = skill.lower()
            if skill_lower not in key_skills and skill_lower not in description:
                if skill_lower not in name:
                    missing.append(skill)

        return missing

    def _check_excluded_keywords(self, vacancy: dict) -> list[str]:
        """Check if vacancy contains any excluded keywords."""
        if not self.request.excluded_keywords:
            return []

        description = vacancy.get("description", "").lower()
        name = vacancy.get("name", "").lower()

        found = []
        for keyword in self.request.excluded_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in description or keyword_lower in name:
                found.append(keyword)

        return found
