import asyncio
import sentry_sdk
from uuid import UUID
from fastapi import FastAPI
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from starlette.middleware.sessions import SessionMiddleware


from app.limiter import limiter
from app.api.routers import router
from app.core.security import Security
from app.core.config import get_settings
from app.api.services.event import EventBus
from app.database.session import get_session
from app.database.session import redis_client
from app.api.repo.redis import RedisRepository
from app.api.schemas.event import TypingResponse
from app.api.repo.document import DocumentRepository
from app.api.services.document import DocumentService
from app.api.services.websocket import WebSocketService
from app.core.exception_handlers import ExceptionHandler
from app.api.repo.document_member import DocumentMemberRepository
from app.api.schemas.websocket import WebSocket as WebsocketSchema
from app.api.services.connection_registry import ConnectionRegistry

SECURITY = Security()
SETTINGS = get_settings()

sentry_sdk.init(
    dsn=SETTINGS.SENTRY_SDK_DSN,
    enable_logs=True,
    send_default_pii=True,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    profile_lifecycle="trace",
)


async def session():
    return await anext(get_session())


async def document_service(app: FastAPI) -> DocumentService:
    return DocumentService(
        redis_repo=RedisRepository(async_redis=app.state.redis),
        doc_repo=DocumentRepository(async_session=await session()),
        member_repo=DocumentMemberRepository(async_session=await session()),
    )


async def websocket_service(app: FastAPI):
    return WebSocketService(
        registry=app.state.registry,
        redis=RedisRepository(async_redis=app.state.redis),
    )


async def expired_typing_event(app: FastAPI):
    event_bus: EventBus = app.state.event_bus
    async for message in event_bus.pubsub.listen():
        channel: str = message["channel"]

        if channel.startswith("__keyspace@0__:typing:"):
            parse_key: list = channel.split(":")

            doc_id: str = parse_key[-2]
            user_id: UUID = parse_key[-1]

            typing_response: dict = TypingResponse(
                doc_id=doc_id, user_id=user_id, mode="stopped"
            ).model_dump()
            await event_bus.publish(f"room:{doc_id}", typing_response)


async def expired_presence_event(app: FastAPI):
    doc_service: DocumentService = await document_service(app)
    ws_service: WebSocketService = await websocket_service(app)

    event_bus: EventBus = app.state.event_bus
    registry: ConnectionRegistry = app.state.registry

    async for message in event_bus.pubsub.listen():
        channel: str = message["channel"]

        if channel.startswith("__keyspace@0__:presence:"):
            parse_key: list = channel.split(":")

            doc_id: str = parse_key[-2]
            connection_id: str = parse_key[-1]

            ws_schema: list[WebsocketSchema] = registry.get_connections(doc_id)
            for ws in ws_schema:
                if ws.connection_id == connection_id:
                    await ws_service.cleanup_connection(
                        doc_id, event_bus, ws, doc_service
                    )
                    break


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis_client
    await SECURITY.register_oauth()

    await app.state.redis.config_set("notify-keyspace-events", "Kx")

    app.state.registry = ConnectionRegistry(
        RedisRepository(async_redis=app.state.redis)
    )
    event_bus = EventBus(async_redis=app.state.redis)

    await event_bus.psubscribe("__keyspace@0__:typing:*")
    await event_bus.psubscribe("__keyspace@0__:presence:*")

    t1 = asyncio.create_task(expired_typing_event(app))
    t2 = asyncio.create_task(expired_presence_event(app))

    yield

    await event_bus.punsubscribe("__keyspace@0__:typing:*")
    await event_bus.punsubscribe("__keyspace@0__:presence:*")

    t1.cancel(), t2.cancel()
    asyncio.gather(t1, t2, return_exceptions=True)

    await event_bus.pubsub.aclose()
    await app.state.redis.aclose()


app = FastAPI(
    title=SETTINGS.API_TITLE,
    version=SETTINGS.API_VERSION,
    description=SETTINGS.API_DESCRIPTION,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(router.router)

app.add_middleware(
    SessionMiddleware,
    max_age=900,
    same_site="lax",
    secret_key=SETTINGS.SESSION_SECRET_KEY,
    https_only=SETTINGS.ENVIRONMENT == "production",
)

exception_handler = ExceptionHandler(app)
exception_handler.add_handlers()


@app.get("/", status_code=200)
async def home():
    message: dict = {
        "status": "success",
        "message": "Welcome to Cowrite",
    }
    return message
