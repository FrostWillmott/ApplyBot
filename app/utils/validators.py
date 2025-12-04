"""Validation logic for applications."""

from dataclasses import dataclass, field

from app.schemas.apply import ApplyRequest


@dataclass
class ValidationResult:
    """Result of validation process."""

    is_valid: bool
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


async def validate_application_request(request: ApplyRequest) -> ValidationResult:
    """Validate application request."""
    warnings = []

    if request.resume and len(request.resume.strip()) < 100:
        warnings.append("Resume content is very short")

    if request.skills and len(request.skills.strip()) < 20:
        warnings.append("Skills description is very brief")

    if request.experience and len(request.experience.strip()) < 50:
        warnings.append("Experience description is quite short")

    if not request.resume_id or not request.resume_id.strip():
        return ValidationResult(
            is_valid=False,
            error="Resume ID is required for application submission",
        )

    template_indicators = ["lorem ipsum", "sample text", "template"]
    content = (
        f"{request.resume or ''} {request.skills or ''} {request.experience or ''}"
    )
    content_lower = content.lower()

    for indicator in template_indicators:
        if indicator in content_lower:
            return ValidationResult(
                is_valid=False,
                error=f"Template content detected: {indicator}",
            )

    return ValidationResult(is_valid=True, warnings=warnings)


def validate_bulk_application_limits(
    max_applications: int,
    user_daily_limit: int = 100,
) -> ValidationResult:
    """Validate bulk application limits."""
    if max_applications > user_daily_limit:
        return ValidationResult(
            is_valid=False,
            error=f"Cannot exceed daily limit of {user_daily_limit} applications",
        )

    if max_applications > 50:
        return ValidationResult(
            is_valid=True,
            warnings=[
                f"High application count ({max_applications}) may trigger rate limits"
            ],
        )

    return ValidationResult(is_valid=True)
