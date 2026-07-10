import httpx
import pytest
from uuid import uuid7


def get_document_payload():
    return {"title": "Test document title", "content": "Test document content"}


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_document(
        async_client: httpx.AsyncClient, login: httpx.Response
    ):
        document_payload: dict = get_document_payload()
        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.post(
            "/documents",
            json={"document_payload": document_payload},
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 201
        assert json_res["data"]["title"] == document_payload["title"]

    @pytest.mark.asyncio
    async def test_invalid_payload(
        async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.post(
            "/documents",
            json={"document_payload": {"title": "", "content": ""}},
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_unauthorized_create_document(async_client: httpx.AsyncClient):
        document_payload: dict = get_document_payload()

        res: httpx.Response = await async_client.post(
            "/documents",
            json={"document_payload": document_payload},
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_get_document(async_client: httpx.AsyncClient, login: httpx.Response):
        document_payload: dict = get_document_payload()
        access_token = login.json()["data"]["access_token"]

        create_res = await async_client.post(
            "/documents",
            json={"document_payload": document_payload},
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        document_id: str = create_res["data"]["id"]

        res: httpx.Response = await async_client.get(
            f"/documents/{document_id}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["id"] == document_id

    @pytest.mark.asyncio
    async def test_get_document_not_found(
        async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.get(
            f"/documents/{uuid7()}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_get_document(
        async_client: httpx.AsyncClient, login: httpx.Response
    ):
        document_payload: dict = get_document_payload()
        access_token = login.json()["data"]["access_token"]

        create_res = await async_client.post(
            "/documents",
            json={"document_payload": document_payload},
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        document_id: str = create_res["data"]["id"]

        res: httpx.Response = await async_client.get(
            f"/documents/{document_id}", headers={"env": "test"}
        )

        assert res.status_code == 401
