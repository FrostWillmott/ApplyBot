"""Background tasks for ApplyBot job application automation.

This module handles asynchronous job application processing using RQ (Redis Queue).
Tasks include vacancy processing, application generation, and submission to HH.ru.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from redis import Redis
from rq import Queue, Worker
from rq.job import Job

from app.core.storage import TokenStorage
from app.schemas.apply import ApplyRequest, BulkApplyRequest
from app.services.application_service import ApplicationService
from app.services.hh_client import HHClient
from app.services.llm.factory import get_llm_provider

# Redis connection and queue setup
redis_conn = Redis.from_url("redis://redis:6379/0")
applybot_queue = Queue("applybot", connection=redis_conn)

logger = logging.getLogger(__name__)


# Core Task Functions
def enqueue_single_application(
        vacancy_id: str,
        application_request: dict[str, Any],
        user_id: str = None
) -> Job:
    """Enqueue a single job application task.

    Args:
        vacancy_id: HH.ru vacancy ID
        application_request: Application data matching ApplyRequest schema
        user_id: Optional user identifier for tracking

    Returns:
        RQ Job object for tracking status
    """
    logger.info(f"Enqueueing single application for vacancy {vacancy_id}")

    job = applybot_queue.enqueue(
        process_single_application,
        vacancy_id,
        application_request,
        user_id,
        job_timeout="5m",  # 5 minute timeout per application
        description=f"Apply to vacancy {vacancy_id}"
    )

    return job


def enqueue_bulk_application(
        bulk_request: dict[str, Any],
        max_applications: int = 20,
        user_id: str = None
) -> Job:
    """Enqueue a bulk job application task.

    Args:
        bulk_request: Bulk application data matching BulkApplyRequest schema
        max_applications: Maximum number of applications to submit
        user_id: Optional user identifier for tracking

    Returns:
        RQ Job object for tracking status
    """
    logger.info(f"Enqueueing bulk application for position: {bulk_request.get('position')}")

    job = applybot_queue.enqueue(
        process_bulk_application,
        bulk_request,
        max_applications,
        user_id,
        job_timeout="30m",  # 30 minute timeout for bulk operations
        description=f"Bulk apply for {bulk_request.get('position', 'Unknown Position')}"
    )

    return job


# Task Implementation Functions
def process_single_application(
        vacancy_id: str,
        application_request: dict[str, Any],
        user_id: str = None
) -> dict[str, Any]:
    """Process a single job application in the background.

    This function runs in the RQ worker process and handles the complete
    application workflow for a single vacancy.
    """
    logger.info(f"Processing single application for vacancy {vacancy_id}")

    try:
        # Run async application logic in event loop
        result = asyncio.run(_apply_to_single_vacancy_async(
            vacancy_id, application_request, user_id
        ))

        logger.info(f"Single application completed: {result['status']} for vacancy {vacancy_id}")
        return result

    except Exception as e:
        logger.error(f"Single application failed for vacancy {vacancy_id}: {e!s}")
        return {
            "vacancy_id": vacancy_id,
            "status": "error",
            "error_detail": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def process_bulk_application(
        bulk_request: dict[str, Any],
        max_applications: int = 20,
        user_id: str = None
) -> dict[str, Any]:
    """Process bulk job applications in the background.

    This function handles searching for vacancies and applying to multiple
    positions based on the provided criteria.
    """
    position = bulk_request.get("position", "Unknown Position")
    logger.info(f"Processing bulk application for position: {position}")

    try:
        # Run async bulk application logic in event loop
        results = asyncio.run(_process_bulk_application_async(
            bulk_request, max_applications, user_id
        ))

        success_count = sum(1 for r in results if r.get("status") == "success")
        logger.info(f"Bulk application completed: {success_count}/{len(results)} successful applications")

        return {
            "status": "completed",
            "total_applications": len(results),
            "successful_applications": success_count,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Bulk application failed for position {position}: {e!s}")
        return {
            "status": "error",
            "error_detail": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Async Helper Functions
async def _apply_to_single_vacancy_async(
        vacancy_id: str,
        application_request: dict[str, Any],
        user_id: str = None
) -> dict[str, Any]:
    """Async implementation of single vacancy application."""
    # Initialize clients and services
    async with HHClient() as hh_client:
        llm_provider = get_llm_provider()
        app_service = ApplicationService(hh_client, llm_provider)

        # Convert dict to Pydantic model
        request = ApplyRequest(**application_request)

        # Process application
        result = await app_service.apply_to_single_vacancy(
            vacancy_id, request, user_id
        )

        # Convert response to dict for JSON serialization
        return {
            "vacancy_id": result.vacancy_id,
            "status": result.status,
            "vacancy_title": result.vacancy_title,
            "cover_letter": result.cover_letter,
            "error_detail": result.error_detail,
            "timestamp": datetime.utcnow().isoformat()
        }


async def _process_bulk_application_async(
        bulk_request: dict[str, Any],
        max_applications: int,
        user_id: str = None
) -> list[dict[str, Any]]:
    """Async implementation of bulk application processing."""
    # Initialize clients and services
    async with HHClient() as hh_client:
        llm_provider = get_llm_provider()
        app_service = ApplicationService(hh_client, llm_provider)

        # Convert dict to Pydantic model
        request = BulkApplyRequest(**bulk_request)

        # Process bulk applications
        results = await app_service.bulk_apply(
            request, max_applications, user_id
        )

        # Convert responses to dicts for JSON serialization
        return [
            {
                "vacancy_id": result.vacancy_id,
                "status": result.status,
                "vacancy_title": result.vacancy_title,
                "cover_letter": result.cover_letter,
                "error_detail": result.error_detail,
            }
            for result in results
        ]


# Monitoring and Management Functions
def get_queue_status() -> dict[str, Any]:
    """Get current queue status and statistics."""
    return {
        "queue_name": applybot_queue.name,
        "pending_jobs": len(applybot_queue),
        "failed_jobs": len(applybot_queue.failed_job_registry),
        "workers": len(Worker.all(connection=redis_conn)),
        "timestamp": datetime.utcnow().isoformat()
    }


def cleanup_completed_jobs(max_age_hours: int = 24) -> int:
    """Clean up old completed jobs from the queue.

    Args:
        max_age_hours: Maximum age of jobs to keep in hours

    Returns:
        Number of jobs cleaned up
    """
    registry = applybot_queue.finished_job_registry
    cleanup_count = registry.cleanup(max_age_hours * 3600)  # Convert to seconds

    logger.info(f"Cleaned up {cleanup_count} completed jobs older than {max_age_hours} hours")
    return cleanup_count


def retry_failed_jobs() -> int:
    """Retry all failed jobs in the queue.

    Returns:
        Number of jobs requeued for retry
    """
    failed_registry = applybot_queue.failed_job_registry
    job_ids = failed_registry.get_job_ids()

    retry_count = 0
    for job_id in job_ids:
        try:
            failed_registry.requeue(job_id)
            retry_count += 1
        except Exception as e:
            logger.error(f"Failed to retry job {job_id}: {e!s}")

    logger.info(f"Requeued {retry_count} failed jobs for retry")
    return retry_count


# Scheduled Tasks (for use with RQ Scheduler)
def daily_cleanup_task():
    """Daily maintenance task to clean up old jobs and logs."""
    logger.info("Running daily cleanup task")

    # Clean up completed jobs older than 24 hours
    cleanup_completed_jobs(max_age_hours=24)

    # Clean up failed jobs older than 7 days
    failed_registry = applybot_queue.failed_job_registry
    failed_registry.cleanup(7 * 24 * 3600)  # 7 days in seconds

    logger.info("Daily cleanup task completed")


def token_refresh_task():
    """Periodic task to check and refresh HH.ru tokens."""
    logger.info("Running token refresh check")

    try:
        # This would run the token refresh logic
        # Implementation depends on your token management strategy
        asyncio.run(_check_and_refresh_tokens())
        logger.info("Token refresh check completed")
    except Exception as e:
        logger.error(f"Token refresh check failed: {e!s}")


async def _check_and_refresh_tokens():
    """Check if tokens need refreshing and refresh if necessary."""
    token = await TokenStorage.get_latest()

    if not token:
        logger.warning("No tokens found in storage")
        return

    if token.is_expired():
        logger.warning("Token is expired - manual re-authentication required")
        # In a real implementation, you might want to send notifications
        # or trigger an automated refresh flow
    else:
        logger.info("Token is still valid")


# Worker Configuration
def start_worker(burst: bool = False):
    """Start an RQ worker for processing ApplyBot tasks.

    Args:
        burst: If True, worker will exit when queue is empty
    """
    logger.info("Starting ApplyBot worker")

    worker = Worker(
        [applybot_queue],
        connection=redis_conn,
        name="applybot-worker"
    )

    worker.work(burst=burst)


if __name__ == "__main__":
    # Run worker if script is executed directly
    import sys

    burst_mode = "--burst" in sys.argv
    start_worker(burst=burst_mode)
