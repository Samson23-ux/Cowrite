import sentry_sdk
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
from app.database.session import redis_client
from app.core.exception_handlers import ExceptionHandler
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await SECURITY.register_oauth()
    app.state.redis = redis_client
    app.state.registry = ConnectionRegistry()
    app.state.event_bus = EventBus(async_redis=app.state.redis)

    yield

    await app.state.redis.aclose()
    await app.state.event_bus._async_pubsub.aclose()


app = FastAPI(
    title=SETTINGS.API_TITLE,
    version=SETTINGS.API_VERSION,
    description=SETTINGS.API_DESCRIPTION,
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
