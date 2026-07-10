import json
import base64
from uuid import uuid4
from typing import Optional
from jose import jwt, JWTError
from binascii import Error as binascii_error
from pwdlib.hashers.argon2 import Argon2Hasher
from datetime import datetime, timezone, timedelta
from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings
from app.api.schemas.auth import TokenData


class Security:
    SETTINGS = get_settings()

    def __init__(self):
        self.oauth: OAuth = OAuth()
        self.arg2_hasher = Argon2Hasher()

    async def register_oauth(self):
        self.oauth.register(
            name="google",
            client_id=self.SETTINGS.GOOGLE_CLIENT_ID,
            client_secret=self.SETTINGS.GOOGLE_CLIENT_SECRET,
            server_metadata_url=self.SETTINGS.GOOGLE_OAUTH_URL,
            client_kwargs={
                "scope": "openid email",
            },
        )

    async def encode_cursor(self, payload: dict) -> str:
        payload_string: str = json.dumps(payload)
        return base64.b64encode(payload_string.encode()).decode()

    async def decode_cursor(self, cursor_string: str, curr_order: str) -> dict:
        try:
            if not cursor_string:
                return

            cursor_string = base64.b64decode(cursor_string)
            cursor_payload = json.loads(cursor_string)

            if cursor_payload["order"] != curr_order.lower():
                return
            return cursor_payload
        except json.JSONDecodeError, UnicodeDecodeError, binascii_error:
            return

    async def hash_password(self, password: str) -> str:
        password: str = password + self.SETTINGS.ARGON2_PASSWORD_PEPPER
        return self.arg2_hasher.hash(password)

    async def verify_password(self, password: str, hash_password: str) -> bool:
        password: str = password + self.SETTINGS.ARGON2_PASSWORD_PEPPER
        return self.arg2_hasher.verify(password, hash_password)

    async def create_access_token(
        self, token_data: TokenData, expire_time: Optional[int] = None
    ) -> str:
        if not expire_time:
            expire_time: datetime = datetime.now(timezone.utc) + timedelta(
                minutes=self.SETTINGS.ACCESS_TOKEN_EXPIRE_TIME
            )
        else:
            expire_time: datetime = datetime.now(timezone.utc) + timedelta(
                minutes=expire_time
            )

        payload: dict = {
            "sub": token_data.email,
            "exp": expire_time,
            "iat": datetime.now(timezone.utc),
            "usertype": token_data.user_type,
        }

        token: str = jwt.encode(
            claims=payload,
            key=self.SETTINGS.ACCESS_TOKEN_SECRET_KEY,
            algorithm=self.SETTINGS.JWT_ALGORITHM,
        )

        return token

    async def create_refresh_token(
        self, token_data: TokenData, expire_time: Optional[int] = None
    ) -> tuple:
        if not expire_time:
            expire_time: datetime = datetime.now(timezone.utc) + timedelta(
                days=self.SETTINGS.REFRESH_TOKEN_EXPIRE_TIME
            )
        else:
            expire_time: datetime = datetime.now(timezone.utc) + timedelta(
                days=expire_time
            )

        payload: dict = {
            "sub": token_data.email,
            "exp": expire_time,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "usertype": token_data.user_type,
        }

        token: str = jwt.encode(
            claims=payload,
            key=self.SETTINGS.REFRESH_TOKEN_SECRET_KEY,
            algorithm=self.SETTINGS.JWT_ALGORITHM,
        )

        return token, payload["jti"], payload["usertype"]

    async def decode_token(self, token: str, key: str):
        try:
            if token is None:
                return

            payload: dict = jwt.decode(
                token=token, key=key, algorithms=[self.SETTINGS.JWT_ALGORITHM]
            )
            return payload
        except JWTError:
            return

    async def prepare_tokens(self, token_data: TokenData):
        access_token: str = await self.create_access_token(token_data)
        refresh_token, refresh_token_id, user_type = await self.create_refresh_token(
            token_data
        )

        refresh_token_expire_time: int = (
            get_settings().REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600
        )

        refresh_token_payload: dict = {
            "email": token_data.email,
            "user_type": user_type,
            "refresh_token_id": refresh_token_id,
            "refresh_token": refresh_token,
            "refresh_token_expire_time": refresh_token_expire_time,
        }

        return access_token, refresh_token_payload
