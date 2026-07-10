import resend
import sentry_sdk
from uuid import UUID
import sentry_sdk.logger as sentry_logger

from app.api.models.email import Email
from app.api.schemas.email import EmailInDB
from app.core.exceptions import ServerError
from app.api.repo.email import EmailRepository


class EmailService:
    def __init__(self, email_repo: EmailRepository):
        self._api_key = None
        self._email_repo = email_repo

    async def create_email(self, email_payload: EmailInDB):
        try:
            self._email_repo.add(entity=email_payload)
            await self._email_repo.commit()
        except Exception as e:
            await self._email_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating email record",
            )
            raise ServerError() from e

    def get_processed_email(self, email_id: UUID) -> Email | None:
        email: Email | None = self._email_repo.get_sync_record(id=email_id)
        return email

    def update_processed_email(self, email: Email):
        try:
            self._email_repo.sync_add(model=email)
            self._email_repo.sync_commit()
        except Exception as e:
            self._email_repo.sync_rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while updating email record",
            )
            raise ServerError() from e

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, api_key: str):
        self._api_key = api_key
        resend.api_key = self._api_key

    def send(self, sender: str, recipient: str, subject: str, body: str):
        resend.Emails.send(
            {
                "from": sender,
                "to": recipient,
                "subject": subject,
                "html": body,
            }
        )
