import pytest
from uuid import uuid7
from sqlalchemy import text
from redis.asyncio import Redis
from sqlalchemy.pool import NullPool
from asgi_lifespan import LifespanManager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
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
from app.api.repo.otp import OtpRepository
from app.database.session import get_session
from app.api.services.auth import AuthService
from app.api.repo.redis import RedisRepository
from app.deps import (
    get_auth_service,
    get_redis_client,
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
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


@pytest.fixture
async def session_maker(async_engine: AsyncEngine):
    async_connection: AsyncConnection = await async_engine.connect()
    async_transaction: AsyncTransaction = await async_connection.begin()

    session = async_sessionmaker(
        bind=async_connection,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        # join_transaction_mode="create_savepoint",
    )

    yield session

    await async_transaction.rollback()
    await async_connection.close()

from redis.asyncio.connection import ConnectionPool


@pytest.fixture(scope="session")
async def redis_pool():
    try:
        pool: ConnectionPool = ConnectionPool.from_url(
            get_settings().REDIS_URL, decode_responses=True, max_connections=20
        )
        yield pool
    finally:
        await pool.disconnect()


@pytest.fixture
async def test_redis_client(redis_pool: ConnectionPool):
    try:
        redis_client: Redis = Redis(
            connection_pool=redis_pool
        )
        yield redis_client
    finally:
        await redis_client.aclose()


@pytest.fixture(autouse=True)
async def flush_redis(test_redis_client: Redis):
    yield
    await test_redis_client.flushdb()


@pytest.fixture
async def lifespan_manager():
    async with LifespanManager(app) as manager:
        yield manager


@pytest.fixture
async def async_client(
    session_maker: async_sessionmaker[AsyncSession],
    test_redis_client: Redis,
    lifespan_manager: LifespanManager,
):
    async def get_test_session():
        session = session_maker()
        yield session
        await session.aclose()

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_redis_client] = lambda: test_redis_client

    async with AsyncClient(
        transport=ASGITransport(lifespan_manager.app),
        base_url="http://localhost/api/v1",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def websocket_client(
    session_maker: async_sessionmaker[AsyncSession],
    test_redis_client: Redis,
    lifespan_manager: LifespanManager,
):
    async def get_test_session():
        session = session_maker()
        yield session
        await session.aclose()

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_redis_client] = lambda: test_redis_client

    async with AsyncClient(
        transport=ASGIWebSocketTransport(lifespan_manager.app)
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def create_user(async_client: AsyncClient):
    path: str = "app.api.services.auth.send_verification_email.apply_async"

    sign_up_payload: dict = {
        "email": "user@example.com",
        "display_name": "test_user",
        "password": "test_user_password",
    }

    with patch(path) as email_patch:
        res_1: Response = await async_client.post(
            "/auth/signup",
            json=sign_up_payload,
            headers={"env": "test"},
        )

        sign_up_payload["email"] = "user1@example.com"
        sign_up_payload["display_name"] = "test_user1"

        res_2: Response = await async_client.post(
            "/auth/signup",
            json=sign_up_payload,
            headers={"env": "test"},
        )

    email_patch.assert_called()

    return res_1, res_2


def mock_auth_service(fake_otp: Otp, redis: Redis):
    otp_repo = MagicMock(spec=OtpRepository)
    redis = RedisRepository(async_redis=redis)

    otp_repo.get_record = AsyncMock(return_value=fake_otp)
    auth_service = AuthService(otp_repo=otp_repo, redis_repo=redis)

    app.dependency_overrides[get_auth_service] = lambda: auth_service


@pytest.fixture
async def verify_user(
    async_client: AsyncClient, create_user: tuple[Response], test_redis_client: Redis
):
    fake_otp: Otp = Otp(
        id=uuid7(),
        otp="test_otp_token",
        user_id=uuid7(),
        status="valid",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )

    otp_payload_1: dict = {
        "email": "user@example.com",
        "otp_code": "test_otp_token",
    }

    otp_payload_2: dict = {
        "email": "user1@example.com",
        "otp_code": "test_otp_token",
    }

    mock_auth_service(fake_otp, test_redis_client)

    await async_client.patch(
        "/auth/verify", json=otp_payload_1, headers={"env": "test"}
    )

    await async_client.patch(
        "/auth/verify", json=otp_payload_2, headers={"env": "test"}
    )


@pytest.fixture
async def login(async_client: AsyncClient, verify_user):
    login_payload_1: dict = {
        "email": "user@example.com",
        "password": "test_user_password",
    }

    login_payload_2: dict = {
        "email": "user1@example.com",
        "password": "test_user_password",
    }

    res_1: Response = await async_client.post(
        "/auth/login",
        json=login_payload_1,
        headers={"env": "test"},
    )

    res_2: Response = await async_client.post(
        "/auth/login",
        json=login_payload_2,
        headers={"env": "test"},
    )

    return res_1, res_2
