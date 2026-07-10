from uuid import UUID
from fastapi import WebSocket
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr


class WebSocket(BaseModel):
    websocket: WebSocket
    user_id: UUID
    user_email: EmailStr
    joined_at: datetime = datetime.now(timezone.utc)
