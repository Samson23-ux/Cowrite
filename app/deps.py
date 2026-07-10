from typing import Annotated
from redis.asyncio import Redis
from fastapi import Depends, Request
import sentry_sdk.logger as sentry_logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.api.models.user import User
from app.core.security import Security
from app.core.config import get_settings
from app.api.repo.otp import OtpRepository
from app.database.session import get_session
from app.api.repo.user import UserRepository
from app.api.services.auth import AuthService
from app.api.services.user import UserService
from app.api.repo.email import EmailRepository
from app.api.repo.redis import RedisRepository
from app.api.services.email import EmailService
from app.api.repo.uow import UnitOfWorkRepository
from app.core.exceptions import AuthenticationError
from app.api.repo.document import DocumentRepository
from app.api.services.document import DocumentService

# Auth bearer
bearer = HTTPBearer(auto_error=False)

# ------------------- DB dependency ------------------------------ #

DBSession = Annotated[AsyncSession, Depends(get_session)]


# ------------------- Redis dependency ------------------------------ #
async def get_redis_client(request: Request) -> Redis:
    redis_client: Redis = request.app.state.redis
    return redis_client


RedisDep = Annotated[Redis, Depends(get_redis_client)]


# ------------------- Security dependency ------------------------------ #
async def get_security() -> Security:
    return Security()


SecurityDep = Annotated[Security, Depends(get_security)]

#  ------------------- Repo dependency ----------------------------- #


async def get_otp_repo(session: DBSession) -> OtpRepository:
    return OtpRepository(async_session=session)


async def get_user_repo(session: DBSession) -> UserRepository:
    return UserRepository(async_session=session)


async def get_redis_repo(redis: RedisDep) -> RedisRepository:
    return RedisRepository(async_redis=redis)


async def get_email_repo(session: DBSession) -> EmailRepository:
    return EmailRepository(async_session=session)


async def get_unit_of_work(session: DBSession) -> UnitOfWorkRepository:
    return UnitOfWorkRepository(session=session)


async def get_document_repo(session: DBSession) -> DocumentRepository:
    return DocumentRepository(async_session=session)


OtpRepo = Annotated[OtpRepository, Depends(get_otp_repo)]
UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
RedisRepo = Annotated[RedisRepository, Depends(get_redis_repo)]
EmailRepo = Annotated[EmailRepository, Depends(get_email_repo)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repo)]
UnitOfWorkRepo = Annotated[UnitOfWorkRepository, Depends(get_unit_of_work)]

#  -------------------- Service dependency ---------------------------- #


async def get_user_service(user_repo: UserRepo) -> UserService:
    return UserService(user_repo=user_repo)


async def get_email_service(email_repo: EmailRepo) -> EmailService:
    return EmailService(email_repo=email_repo)


async def get_auth_service(otp_repo: OtpRepo, redis_repo: RedisRepo) -> AuthService:
    return AuthService(otp_repo=otp_repo, redis_repo=redis_repo)


async def get_document_service(doc_repo: DocumentRepo) -> DocumentService:
    return DocumentService(doc_repo=doc_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]

# ------------------------ Auth dependency ---------------------------- #


async def get_current_user(
    user_service: UserServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> User:
    security: Security = Security()
    if not credentials:
        sentry_logger.error("User not authenticated")
        raise AuthenticationError()

    token: str | None = credentials.credentials
    key: str = get_settings().ACCESS_TOKEN_SECRET_KEY

    payload: dict = await security.decode_token(token, key)

    if not payload:
        sentry_logger.error("User not authenticated")
        raise AuthenticationError()

    user_email: str = payload.get("sub")
    user_type: str = payload.get("usertype")

    if user_type == "email":
        user: User = await user_service.get_user_by_email(
            email=user_email, is_verified=True
        )
    else:
        user: User = await user_service.get_user_by_email(
            google_email=user_email, is_verified=True
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(curr_user: CurrentUser):
    if curr_user.is_active is False:
        raise AuthenticationError()
    return curr_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
