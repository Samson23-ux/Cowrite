from fastapi import Query
from typing import Annotated
from redis.asyncio import Redis
import sentry_sdk.logger as sentry_logger
from fastapi.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, WebSocketException, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.api.models.user import User
from app.core.security import Security
from app.core.config import get_settings
from app.api.repo.otp import OtpRepository
from app.api.services.event import EventBus
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
from app.api.services.websocket import WebSocketService
from app.api.services.transformation import Transformation
from app.api.repo.document_member import DocumentMemberRepository

# Auth bearer
bearer = HTTPBearer(auto_error=False)

# ------------------- DB dependency ------------------------------ #

DBSession = Annotated[AsyncSession, Depends(get_session)]


# ------------------- Redis dependency ------------------------------ #
async def get_redis_client(request: HTTPConnection) -> Redis:
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


async def get_member_repo(session: DBSession) -> DocumentMemberRepository:
    return DocumentMemberRepository(async_session=session)


OtpRepo = Annotated[OtpRepository, Depends(get_otp_repo)]
UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
RedisRepo = Annotated[RedisRepository, Depends(get_redis_repo)]
EmailRepo = Annotated[EmailRepository, Depends(get_email_repo)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repo)]
MemberRepo = Annotated[DocumentMemberRepository, Depends(get_member_repo)]
UnitOfWorkRepo = Annotated[UnitOfWorkRepository, Depends(get_unit_of_work)]

#  -------------------- Service dependency ---------------------------- #


async def get_user_service(user_repo: UserRepo) -> UserService:
    return UserService(user_repo=user_repo)


async def get_email_service(email_repo: EmailRepo) -> EmailService:
    return EmailService(email_repo=email_repo)


async def get_auth_service(otp_repo: OtpRepo, redis_repo: RedisRepo) -> AuthService:
    return AuthService(otp_repo=otp_repo, redis_repo=redis_repo)


async def get_document_service(
    doc_repo: DocumentRepo, member_repo: MemberRepo, redis_repo: RedisRepo
) -> DocumentService:
    return DocumentService(
        doc_repo=doc_repo, member_repo=member_repo, redis_repo=redis_repo
    )


async def get_event_bus(websocket: WebSocket) -> EventBus:
    return EventBus(websocket.app.state.redis)


async def get_websocket_service(
    websocket: WebSocket, redis_repo: RedisRepo
) -> WebSocketService:
    registry = websocket.app.state.registry
    return WebSocketService(registry=registry, redis=redis_repo)


async def get_transformation() -> Transformation:
    return Transformation()


EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]
TransformationDep = Annotated[Transformation, Depends(get_transformation)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
WebSocketServiceDep = Annotated[WebSocketService, Depends(get_websocket_service)]

# ------------------------ Auth dependency ---------------------------- #


async def get_current_user(
    security: SecurityDep,
    user_service: UserServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> User:
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


async def authenticate_websocket_connection(
    security: SecurityDep,
    user_service: UserServiceDep,
    token: Annotated[str | None, Query()] = None,
) -> tuple[User, str]:
    if not token:
        sentry_logger.error("User not authenticated")
        raise WebSocketException(code=1008, reason="User not authenticated")

    key: str = get_settings().ACCESS_TOKEN_SECRET_KEY
    payload: dict = await security.decode_token(token, key)

    if not payload:
        sentry_logger.error("User not authenticated")
        raise WebSocketException(code=1008, reason="User not authenticated")

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

    if user.is_active is False:
        raise WebSocketException(code=1008, reason="User not authenticated")
    return user, user_email


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
WebSocketAuth = Annotated[tuple[User, str], Depends(authenticate_websocket_connection)]
