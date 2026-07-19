from fastapi import WebSocket
from pydantic import BaseModel, EmailStr, ConfigDict


class WebSocket(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection_id: str
    websocket: WebSocket
    user_id: str
    user_email: EmailStr
    joined_at: str
