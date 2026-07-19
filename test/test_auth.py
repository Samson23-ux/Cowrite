import httpx
import pytest
import secrets
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app.deps import get_security
from app.core.security import Security


def get_security_mock():
    payload: dict = {
        "sub": "randomfakeid",
        "name": "test_user",
        "email": "user@example.com",
    }

    refresh_token_payload: dict = {
        "email": "user@example.com",
        "user_type": "google",
        "refresh_token_id": str(uuid4()),
        "refresh_token": secrets.token_urlsafe(32),
        "refresh_token_expire_time": (datetime.now() + timedelta(days=1)).isoformat(),
    }

    token: dict = {"userinfo": payload}
    access_token: str = secrets.token_urlsafe(32)

    security = MagicMock(
        spec=Security()
    )  # pass an instance of the Security class to register instance attributes

    security.oauth.google.authorize_redirect = AsyncMock(return_value=None)
    security.oauth.google.authorize_access_token = AsyncMock(return_value=token)
    security.prepare_tokens = AsyncMock(
        return_value=(access_token, refresh_token_payload)
    )

    return security


class TestSignUpWithEmail:
    @pytest.mark.anyio
    async def test_sign_up(self, create_user: tuple[httpx.Response]):
        create_res, _ = create_user
        json_res = create_res.json()

        assert create_res.status_code == 201
        assert json_res["message"] == (
            "Sign up completed successfully."
            "Check your email for verification code and instructions"
        )

    @pytest.mark.anyio
    async def test_user_exists(
        self, async_client: httpx.AsyncClient, verify_user
    ):
        sign_up_payload: dict = {
            "email": "user@example.com",
            "display_name": "test_user",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 409

    @pytest.mark.anyio
    async def test_invalid_email(self, async_client: httpx.AsyncClient):
        sign_up_payload: dict = {
            "email": "invalid_user_email",
            "display_name": "test_user",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 422


class TestLogin:
    @pytest.mark.anyio
    async def test_login(self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]):
        login_res, _ = login
        json_res = login_res.json()

        assert login_res.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.anyio
    async def test_user_not_verified(
        self, async_client: httpx.AsyncClient, create_user: tuple[httpx.Response]
    ):
        login_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_wrong_email_login(
        self, async_client: httpx.AsyncClient, verify_user
    ):
        login_payload: dict = {
            "email": "user@example123.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestSignUpWithGoogle:
    @pytest.mark.anyio
    async def test_sign_in_google(self, async_client: httpx.AsyncClient):
        app.dependency_overrides[get_security] = lambda: get_security_mock()

        url_path: str = "app.api.routers.auth.Request.url_for"
        with patch(url_path, new_callable=AsyncMock) as url_patch:
            res: httpx.Response = await async_client.get(
                "/auth/google", headers={"env": "test"}
            )

        assert res.status_code == 302

        url_patch.assert_called_once()

    @pytest.mark.anyio
    async def test_google_callback(self, async_client: httpx.AsyncClient):
        app.dependency_overrides[get_security] = lambda: get_security_mock()

        res: httpx.Response = await async_client.get(
            "/auth/google/callback", headers={"env": "test"}
        )

        json_res = res.json()

        assert res.status_code == 200
        assert "access_token" in json_res["data"]


class TestAuthToken:
    @pytest.mark.anyio
    async def test_get_access_token(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )
        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.anyio
    async def test_unauthorized_get_access_token(
        self, async_client: httpx.AsyncClient, verify_user
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestGetCurrentUser:
    @pytest.mark.anyio
    async def test_get_current_user(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        json_res = res.json()

        assert res.status_code == 200
        assert "user@example.com" == json_res["data"]["email"]

    @pytest.mark.anyio
    async def test_unauthenticated_user(self, async_client: httpx.AsyncClient):
        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestResendOtp:
    @pytest.mark.anyio
    async def test_resend_otp_token(
        self, async_client: httpx.AsyncClient, create_user: tuple[httpx.Response]
    ):
        path: str = "app.api.services.auth.send_verification_email.apply_async"

        resend_otp_payload: dict = {
            "email": "user@example.com",
        }

        with patch(path) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/verify/resend",
                json=resend_otp_payload,
                headers={"env": "test"},
            )

        json_res = res.json()

        email_patch.assert_called_once()

        assert res.status_code == 201
        assert json_res["status"] == "success"

    @pytest.mark.anyio
    async def test_invalid_email_otp_token(
        self, async_client: httpx.AsyncClient, create_user: tuple[httpx.Response]
    ):
        resend_otp_payload: dict = {
            "email": "user@example123.com",
        }

        res: httpx.Response = await async_client.post(
            "/auth/verify/resend",
            json=resend_otp_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestLogout:
    @pytest.mark.anyio
    async def test_logout(self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res = await async_client.post(
            "/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 201

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 401

    @pytest.mark.anyio
    async def test_unauthorized_logout(
        self, async_client: httpx.AsyncClient, verify_user
    ):
        res = await async_client.post(
            "/auth/logout",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestDeleteAccount:
    @pytest.mark.anyio
    async def test_delete_account(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res = await async_client.delete(
            "/auth",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 204

        login_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.anyio
    async def test_unauthorized_delete_account(
        self, async_client: httpx.AsyncClient, verify_user
    ):
        res = await async_client.delete(
            "/auth",
            headers={"env": "test"},
        )

        assert res.status_code == 401
