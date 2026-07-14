from fastapi import APIRouter

from app.core.config import get_settings
from app.api.routers import auth, document, websocket

router = APIRouter(prefix=get_settings().API_PREFIX)

router.include_router(auth.router, tags=["Auth"])
router.include_router(document.router, tags=["Document"])
router.include_router(websocket.router, tags=["Websocket"])
