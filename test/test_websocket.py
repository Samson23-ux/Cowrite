import httpx
import pytest
from uuid import uuid4
from httpx_ws import aconnect_ws
from fastapi import WebSocketException

TIMEOUT = 10
WEBSOCKET_URL = "ws://localhost/api/v1/ws"


@pytest.fixture
async def create_document(async_client: httpx.AsyncClient, login: httpx.Response):
    document_payload: dict = {
        "title": "Test document title",
        "content": "Test document content",
    }
    access_token = login.json()["data"]["access_token"]

    res: httpx.Response = await async_client.post(
        "/documents",
        json={"document_payload": document_payload},
        headers={"Authorization": f"Bearer {access_token}", "env": "test"},
    )
    return res


class TestJoinEvent:
    @pytest.mark.asyncio
    async def test_single_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            payload: dict = {"type": "join", "doc_id": doc_id}
            await client.send_json(payload)

            try:
                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert "seq" in res
            assert res["type"] == "joined"
            assert res["doc_id"] == doc_id

    @pytest.mark.asyncio
    async def test_invalid_payload(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
    ):
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            payload: dict = {"type": "join"}

            with pytest.raises(WebSocketException) as exc:
                await client.send_json(payload)

            assert exc.value.code == 1003
            assert exc.value.reason == "Invalid payload!"

    @pytest.mark.asyncio
    async def test_invalid_doc_id(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
    ):
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            payload: dict = {"type": "join", "doc_id": str(uuid4())}

            with pytest.raises(WebSocketException) as exc:
                await client.send_json(payload)

            assert exc.value.code == 1008
            assert exc.value.reason == "Document not found"

    @pytest.mark.asyncio
    async def test_multiple_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client2,
        ):
            payload: dict = {"type": "join", "doc_id": doc_id}
            await client1.send_json(payload)
            await client2.send_json(payload)

            try:
                # response for client1
                res1 = await client1.receive_json(timeout=TIMEOUT)

                # response for client2
                res2 = await client2.receive_json(timeout=TIMEOUT)
                res3 = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res1["type"] == "joined"
            assert res2["type"] == "user_joined"
            assert res2["display_name"] == "user"
            assert len(res3["users"]) == 2


class TestLeaveEvent:
    @pytest.mark.asyncio
    async def test_single_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            leave_payload: dict = {"type": "leave", "doc_id": doc_id}

            await client.send_json(join_payload)
            await client.send_json(leave_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "presence"
            assert len(res["users"]) == 0

    @pytest.mark.asyncio
    async def test_no_connection(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            leave_payload: dict = {"type": "leave", "doc_id": doc_id}

            with pytest.raises(WebSocketException) as exc:
                await client.send_json(leave_payload)

            assert exc.value.code == 1003
            assert exc.value.reason == "Client disconnected!"


class TestCursorEvent:
    @pytest.mark.asyncio
    async def test_single_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            cursor_payload: dict = {"type": "cursor", "doc_id": doc_id, "pos": 10}

            await client.send_json(join_payload)
            await client.send_json(cursor_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "cursor"
            assert res["pos"] == 10


class TestTypingEvent:
    @pytest.mark.asyncio
    async def test_multiple_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            cursor_payload: dict = {"type": "typing", "doc_id": doc_id}

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            await client1.send_json(cursor_payload)

            try:
                # receive joined and presence responses
                await client1.receive_json(timeout=TIMEOUT)
                await client1.receive_json(timeout=TIMEOUT)

                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "typing"
            assert res["doc_id"] == doc_id


class TestPingEvent:
    @pytest.mark.asyncio
    async def test_single_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            ping_payload: dict = {"type": "ping"}

            await client.send_json(join_payload)
            await client.send_json(ping_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "pong"

    @pytest.mark.asyncio
    async def test_unauthenticated_request(
        self,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        async with aconnect_ws(url=WEBSOCKET_URL, client=websocket_client) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            with pytest.raises(WebSocketException) as exc:
                await client.send_json(join_payload)

            assert exc.value.code == 1008
            assert exc.value.reason == "User not authenticated"


class TestOperationEvent:
    @pytest.mark.asyncio
    async def test_insert_operation(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation: dict = {"kind": "insert", "pos": 0, "text": "hello"}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client.send_json(join_payload)
            await client.send_json(operation_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "ack"
            assert res["doc_id"] == doc_id
            assert res["seq"] == 2

    @pytest.mark.asyncio
    async def test_delete_operation(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation: dict = {"kind": "delete", "pos": 0, "text": "T"}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client.send_json(join_payload)
            await client.send_json(operation_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "ack"
            assert res["doc_id"] == doc_id
            assert res["seq"] == 2

    @pytest.mark.asyncio
    async def test_insert_operation_multiple_clients(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation: dict = {"kind": "insert", "pos": 0, "text": "hello"}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            await client1.send_json(operation_payload)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "operation"
            assert res["doc_id"] == doc_id
            assert res["op"] == operation
            assert res["seq"] == 2

    @pytest.mark.asyncio
    async def test_transformation_logic(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client2,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
            ) as client3,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation1: dict = {"kind": "insert", "pos": 0, "text": "hello"}
            operation_payload1: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation1,
                "base_seq": 1,
            }

            operation2: dict = {"kind": "insert", "pos": 0, "text": "hi"}
            operation_payload2: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation2,
                "base_seq": 1,
            }

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)
            await client3.send_json(join_payload)

            await client3.send_json(operation_payload1)

            await client1.send_json(operation_payload1)
            await client2.send_json(operation_payload2)

            try:
                # receive joined and presence responses
                await client3.receive_json(timeout=TIMEOUT)
                await client3.receive_json(timeout=TIMEOUT)

                op1_res = client3.receive_json(timeout=TIMEOUT)
                op2_res = client3.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert op2_res["type"] == "operation"
            assert op2_res["doc_id"] == doc_id
            assert op2_res["op"] == operation2
            assert op2_res["seq"] == 3


class TestDisconnection:
    @pytest.mark.asyncio
    async def test_single_client(
        self,
        login: httpx.Response,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]
        access_token = login.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            leave_payload: dict = {"type": "leave", "doc_id": doc_id}

            await client.send_json(join_payload)
            await client.send_json(leave_payload)

            await client.receive_json(timeout=TIMEOUT)
            presence_res = await client.receive_json(timeout=TIMEOUT)

            users = presence_res["users"]

            pass

        assert not users
