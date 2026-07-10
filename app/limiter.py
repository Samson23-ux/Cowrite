from uuid import uuid4
from slowapi import Limiter
from fastapi import Request
from slowapi.util import get_remote_address

from app.core.config import get_settings


def get_test_id(request: Request):
    env: str = request.headers.get("env")

    if env == "test":
        return uuid4()
    return get_remote_address


limiter = Limiter(
    key_func=get_test_id,
    default_limits=["5/minute"],
    storage_uri=get_settings().REDIS_URL,
)
