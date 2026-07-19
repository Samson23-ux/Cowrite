import httpx
import pytest
from uuid import uuid7


def get_document_payload():
    content = (
        "Test document content"
        "Morning light revealed small truths: laughter, quiet courage, and shared coffee."
        "We walked narrow streets, trading stories until shadows softened."
        "Each step stitched a fragile map of belonging. Time pulsed gently, promising new doors."
        "Together we learned to carry hope without weight, to love honestly, and to keep moving forward."
    )
    return {"title": "Test document title", "content": content}


class TestCreateDocument:
    @pytest.mark.anyio
    async def test_create_document(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        document_payload: dict = get_document_payload()

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res: httpx.Response = await async_client.post(
            "/documents",
            json=document_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 201
        assert json_res["data"]["title"] == document_payload["title"]

    @pytest.mark.anyio
    async def test_invalid_payload(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res: httpx.Response = await async_client.post(
            "/documents",
            json={"document_payload": {"title": "", "content": ""}},
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 422

    @pytest.mark.anyio
    async def test_unauthorized_create_document(self, async_client: httpx.AsyncClient):
        document_payload: dict = get_document_payload()

        res: httpx.Response = await async_client.post(
            "/documents",
            json=document_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestGetDocument:
    @pytest.mark.anyio
    async def test_get_document(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        document_payload: dict = get_document_payload()

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        create_res = await async_client.post(
            "/documents",
            json=document_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        document_id: str = create_res.json()["data"]["id"]

        res: httpx.Response = await async_client.get(
            f"/documents/{document_id}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["id"] == document_id

    @pytest.mark.anyio
    async def test_get_document_not_found(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        res: httpx.Response = await async_client.get(
            f"/documents/{uuid7()}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    @pytest.mark.anyio
    async def test_unauthorized_get_document(
        self, async_client: httpx.AsyncClient, login: tuple[httpx.Response]
    ):
        document_payload: dict = get_document_payload()

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        create_res = await async_client.post(
            "/documents",
            json=document_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        document_id: str = create_res.json()["data"]["id"]

        res: httpx.Response = await async_client.get(
            f"/documents/{document_id}", headers={"env": "test"}
        )

        assert res.status_code == 401
