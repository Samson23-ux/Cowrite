import pytest_asyncio
from uuid import uuid7
from sqlalchemy import text
from redis.asyncio import Redis
from sqlalchemy.pool import NullPool
from asgi_lifespan import LifespanManager
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta
from httpx_ws.transport import ASGIWebSocketTransport
from httpx import AsyncClient, ASGITransport, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncConnection,
    AsyncTransaction,
)

from app.main import app
from app.api.models.otp import Otp
from app.api.models.base import Base
from app.core.config import get_settings
from app.api import models  # noqa: F401
from app.api.services.auth import AuthService
from app.api.repo.redis import RedisRepository
from app.deps import (
    get_session,
    get_auth_service,
    get_redis_client,
)


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    async_db_engine: AsyncEngine = create_async_engine(
        url=get_settings().ASYNC_TEST_DB_URL, poolclass=NullPool
    )

    async with async_db_engine.begin() as conn:
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION uuid_generate_v7()
                RETURNS UUID
                LANGUAGE SQL
                VOLATILE
                AS $$
                    SELECT encode(
                        set_bit(
                            set_bit(
                                overlay(
                                    uuid_send(gen_random_uuid())
                                    placing substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
                                    FROM 1 FOR 6
                                ),
                                52, 1
                            ),
                            53, 1
                        ),
                        'hex'
                    )::uuid
                $$;
        """))
        await conn.run_sync(Base.metadata.create_all)

    yield async_db_engine

    async with async_db_engine.begin() as conn:
        await conn.execute(text("DROP FUNCTION IF EXISTS uuid_generate_v7 CASCADE"))
        await conn.execute(text("DROP EXTENSION IF EXISTS pgcrypto CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)

    await async_db_engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine: AsyncEngine):
    async_connection: AsyncConnection = await async_engine.connect()
    async_transaction: AsyncTransaction = await async_connection.begin()

    session = async_sessionmaker(
        bind=async_connection,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async_session: AsyncSession = session()
    yield async_session

    await async_session.close()
    await async_transaction.rollback()
    await async_connection.close()


@pytest_asyncio.fixture
async def test_redis_client():
    try:
        redis_client: Redis = Redis.from_url(
            get_settings().REDIS_URL, decode_responses=True
        )
        yield redis_client
    finally:
        await redis_client.aclose()


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(test_redis_client: Redis):
    yield
    await test_redis_client.flushdb()


@pytest_asyncio.fixture
async def async_client(async_session: AsyncSession, test_redis_client: Redis):
    async def get_test_session():
        return async_session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_redis_client] = lambda: test_redis_client

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app), base_url="http://localhost/api/v1"
        ) as client:
            yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def websocket_client(async_session: AsyncSession, test_redis_client: Redis):
    async def get_test_session():
        return async_session

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_redis_client] = lambda: test_redis_client

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGIWebSocketTransport(app)) as client:
            yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_user(async_client: AsyncClient):
    path: str = "app.api.services.auth.send_verification_email.apply_async"

    sign_up_payload: dict = {
        "email": "user@example.com",
        "display_name": "user",
        "password": "test_user_password",
    }

    with patch(path, new_callable=AsyncMock) as email_patch:
        res: Response = await async_client.post(
            "/auth/signup",
            json=sign_up_payload,
            headers={"env": "test"},
        )

    email_patch.assert_called_once()

    return res


def mock_auth_service(fake_otp: Otp, redis: Redis):
    otp_repo = AsyncMock()
    redis = RedisRepository(async_redis=redis)

    otp_repo.get_record = AsyncMock(return_value=fake_otp)
    auth_service = AuthService(otp_repo=otp_repo, redis_repo=redis)

    app.dependency_overrides[get_auth_service] = lambda: auth_service


@pytest_asyncio.fixture
async def verify_user(
    async_client: AsyncClient, create_user: Response, test_redis_client: Redis
):
    fake_otp: Otp = Otp(
        id=uuid7(),
        otp="test_otp_token",
        user_id=uuid7(),
        status="valid",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )

    otp_payload: dict = {
        "email": "user@example.com",
        "otp_code": "test_otp_token",
    }

    mock_auth_service(fake_otp, test_redis_client)

    res: Response = await async_client.patch(
        "/auth/verify",
        json=otp_payload,
        headers={"env": "test"},
    )

    return res


@pytest_asyncio.fixture
async def login(async_client: AsyncClient, verify_user: Response):
    login_payload: dict = {
        "email": "user@example.com",
        "password": "test_user_password",
    }

    res: Response = await async_client.post(
        "/auth/login",
        json=login_payload,
        headers={"env": "test"},
    )

    return res
