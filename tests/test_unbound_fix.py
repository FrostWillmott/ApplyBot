"""Test for UnboundLocalError fix in apply_to_single_vacancy."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.apply import ApplyRequest
from app.services.application_service import ApplicationService


@pytest.mark.asyncio
async def test_apply_when_get_vacancy_fails():
    """Test that apply_to_single_vacancy handles exceptions when vacancy is not fetched.

    This test ensures that the fix for UnboundLocalError is working correctly.
    Before the fix, when get_vacancy_details() raised an exception, the code would
    crash with "cannot access local variable 'vacancy' where it is not associated with a value"
    because vacancy was never initialized.

    After the fix, vacancy is initialized to None, and the error handler correctly
    handles the case where vacancy was never fetched.
    """
    # Setup
    mock_hh_client = AsyncMock()
    mock_llm_provider = AsyncMock()

    # Simulate network error when fetching vacancy details
    mock_hh_client.get_vacancy_details.side_effect = HTTPException(
        status_code=503, detail="Network error: Temporary failure in name resolution"
    )

    service = ApplicationService(mock_hh_client, mock_llm_provider)

    request = ApplyRequest(
        position="Python Developer",
        resume="Test resume",
        skills="Python, FastAPI",
        experience="5 years",
        resume_id="test_resume_123",
    )

    # Execute - this should NOT raise UnboundLocalError
    result = await service.apply_to_single_vacancy(
        vacancy_id="12345", request=request, user_id="test_user"
    )

    # Verify
    assert result.status == "error"
    assert result.vacancy_id == "12345"

    # The key assertion: vacancy_title should be None when vacancy was never fetched
    # (not crash with UnboundLocalError)
    assert result.vacancy_title is None

    # Error detail should contain information about the exception
    assert result.error_detail is not None
    assert len(result.error_detail) > 0
