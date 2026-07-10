import random
from uuid import UUID
from datetime import datetime, timezone

from app.worker import celery_app
from app.api.models.email import Email


class BaseTaskWithFailure(celery_app.Task):
    # maximum retry value
    max_retries = 5

    """
    retry jitter set to True to ensure randomness in retry_backoff value
    this prevents overwhelming when multiple tasks fails simultaneously,
    retrying each task at different time
    """
    retry_jitter = True

    """
    increment retry delay value exponentially
    """
    retry_backoff = 2

    """
    maximum retry backoff - one minute
    """
    retry_backoff_max = 600

    def _backoff_countdown(self):
        retries = self.request.retries
        countdown = min(self.retry_backoff * (2**retries), self.retry_backoff_max)

        if self.retry_jitter:
            countdown = random.randrange(int(countdown * 0.5), int(countdown * 1.5))
        return countdown

    def _handle_failure(self, kwargs):
        from app.worker import get_email_service

        try:
            email_service = get_email_service()

            email_id: UUID = kwargs.get("email_id")
            email: Email = email_service.get_processed_email(email_id)

            email.status = "failed"
            email.failed_at = datetime.now(timezone.utc)
            email_service.update_processed_email(email)
        finally:
            email_service._email_repo.close()
