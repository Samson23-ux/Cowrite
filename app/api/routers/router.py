from fastapi import APIRouter

from app.api.routers import auth
from app.core.config import get_settings

router = APIRouter(prefix=get_settings().API_PREFIX)

router.include_router(auth.router, tags=["Auth"])
