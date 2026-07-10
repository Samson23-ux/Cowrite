import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.user import User
from app.api.schemas.user import UserInDB
from app.api.repo.user import UserRepository
from app.core.exceptions import ServerError, UserNotFoundError


class UserService:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def get_user_by_email(self, **filters) -> User:
        if "email" in filters:
            user_email: str = filters["email"]
        elif "google_email" in filters:
            user_email: str = filters["google_email"]

        try:
            user: User | None = await self._user_repo.get_record(**filters)

            if not user:
                sentry_logger.error(
                    "User not found with email {email}", email=user_email
                )
                raise UserNotFoundError(user_email=user_email)

            return user
        except Exception as e:
            if isinstance(e, UserNotFoundError):
                raise UserNotFoundError(user_email=user_email) from e

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving user with email {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def _get_user_by_email(self, **filters) -> User | None:
        return await self._user_repo.get_record(**filters)

    async def create_user(self, user: UserInDB, email: str):
        try:
            self._user_repo.add(entity=user)
            await self._user_repo.commit()
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating user with email {email}", email=email
            )
            raise ServerError() from e

    async def update_user(self, user: User):
        try:
            self._user_repo.add(model=user)
            await self._user_repo.commit()
            await self._user_repo.refresh(user)
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while updating user with email {email}", email=user.email
            )
            raise ServerError() from e

    async def delete_user(self, user: User):
        try:
            await self._user_repo.delete(user)
            await self._user_repo.commit()
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while deleting user with email {email}", email=user.email
            )
            raise ServerError() from e
