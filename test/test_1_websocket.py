import httpx
import pytest
from uuid import uuid4
from httpx_ws import aconnect_ws, WebSocketDisconnect

TIMEOUT = 5
WEBSOCKET_URL = "/ws"


@pytest.fixture
async def create_document(
    async_client: httpx.AsyncClient, login: tuple[httpx.Response]
):
    content = (
        "Test document content. "
        "Morning light revealed small truths: laughter, quiet courage, and shared coffee. "
        "We walked narrow streets, trading stories until shadows softened. "
        "Each step stitched a fragile map of belonging. Time pulsed gently, promising new doors. "
        "Together we learned to carry hope without weight, to love honestly, and to keep moving forward."
    )

    document_payload: dict = {
        "title": "Test document title",
        "content": content,
    }

    login_res, _ = login
    access_token = login_res.json()["data"]["access_token"]

    res: httpx.Response = await async_client.post(
        "/documents",
        json=document_payload,
        headers={"Authorization": f"Bearer {access_token}", "env": "test"},
    )
    return res


class TestJoinEvent:
    @pytest.mark.anyio()
    async def test_single_client(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

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

    @pytest.mark.anyio
    async def test_invalid_payload(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            payload: dict = {"type": "join"}

            await client.send_json(payload)

            try:
                await client.receive(timeout=TIMEOUT)
            except WebSocketDisconnect as exc:
                assert exc.code == 1003
                assert exc.reason == "Invalid payload!"

    @pytest.mark.anyio
    async def test_invalid_doc_id(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
    ):
        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            payload: dict = {"type": "join", "doc_id": str(uuid4())}

            await client.send_json(payload)

            try:
                await client.receive(timeout=TIMEOUT)
            except WebSocketDisconnect as exc:
                assert exc.code == 1003
                assert exc.reason == "Document not found"

    @pytest.mark.anyio
    async def test_multiple_client(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
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
                res4 = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

        assert res1["type"] == "joined"
        assert res2["type"] == "joined"
        assert res3["type"] == "user_joined"
        assert res3["display_name"] == "test_user"
        assert len(res4["users"]) == 2


class TestLeaveEvent:
    @pytest.mark.anyio
    async def test_leave_room(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            leave_payload: dict = {"type": "leave", "doc_id": doc_id}

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                await client1.send_json(leave_payload)

                res1 = await client2.receive_json(timeout=TIMEOUT)
                res2 = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

        assert res1["type"] == "user_left"
        assert res2["type"] == "presence"
        assert len(res2["users"]) == 1

    @pytest.mark.anyio
    async def test_no_connection(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            leave_payload: dict = {"type": "leave", "doc_id": doc_id}

            try:
                await client.send_json(leave_payload)
            except WebSocketDisconnect as exc:
                assert exc.code == 1008
                assert exc.reason == "Client disconnected!"


class TestCursorEvent:
    @pytest.mark.anyio
    async def test_move_cursor(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            cursor_payload: dict = {"type": "cursor", "doc_id": doc_id, "pos": 10}

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                await client1.send_json(cursor_payload)
                res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "cursor"
            assert res["pos"] == 10


class TestTypingEvent:
    @pytest.mark.anyio
    async def test_typing_event(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            cursor_payload: dict = {"type": "typing", "doc_id": doc_id}

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            # receive joined and presence responses
            await client2.receive_json(timeout=TIMEOUT)
            await client2.receive_json(timeout=TIMEOUT)
            await client2.receive_json(timeout=TIMEOUT)
            await client2.receive_json(timeout=TIMEOUT)

            await client1.send_json(cursor_payload)

            try:
                res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "typing"
            assert res["doc_id"] == doc_id


class TestPingEvent:
    @pytest.mark.anyio
    async def test_single_client(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            ping_payload: dict = {"type": "ping", "doc_id": doc_id}

            await client.send_json(join_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                await client.send_json(ping_payload)
                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "pong"

    @pytest.mark.anyio
    async def test_unauthenticated_request(
        self,
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        try:
            async with aconnect_ws(
                url=f"{WEBSOCKET_URL}?=tgg", client=websocket_client
            ) as client:
                join_payload: dict = {"type": "join", "doc_id": doc_id}
                await client.send_json(join_payload)
        except WebSocketDisconnect as exc:
            assert exc.code == 1008
            assert exc.reason == "User not authenticated"


class TestOperationEvent:
    @pytest.mark.anyio
    async def test_insert_operation(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

        async with aconnect_ws(
            url=f"{WEBSOCKET_URL}?token={access_token}", client=websocket_client
        ) as client:
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation: dict = {"kind": "insert", "pos": 0, "text": "hello "}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client.send_json(join_payload)

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                await client.send_json(operation_payload)
                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "ack"
            assert res["doc_id"] == doc_id
            assert res["seq"] == 2

    @pytest.mark.anyio
    async def test_delete_operation(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res, _ = login
        access_token = login_res.json()["data"]["access_token"]

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

            try:
                # receive joined and presence responses
                await client.receive_json(timeout=TIMEOUT)
                await client.receive_json(timeout=TIMEOUT)

                await client.send_json(operation_payload)
                res = await client.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "ack"
            assert res["doc_id"] == doc_id
            assert res["seq"] == 2

    @pytest.mark.anyio
    async def test_insert_operation_multiple_clients(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation: dict = {"kind": "insert", "pos": 0, "text": "hello "}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                await client1.send_json(operation_payload)

                res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "operation"
            assert res["doc_id"] == doc_id
            assert res["op"] == operation
            assert res["seq"] == 2

    @pytest.mark.anyio
    async def test_transformation_logic(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            join_payload: dict = {"type": "join", "doc_id": doc_id}

            operation1: dict = {"kind": "insert", "pos": 0, "text": "hello "}
            operation_payload1: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation1,
                "base_seq": 1,
            }

            operation2: dict = {"kind": "insert", "pos": 0, "text": "hi "}
            operation_payload2: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation2,
                "base_seq": 1,
            }

            await client1.send_json(join_payload)
            await client2.send_json(join_payload)

            await client1.send_json(operation_payload1)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                await client2.send_json(operation_payload2)
                op2_res = await client2.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert op2_res["type"] == "ack"
            assert op2_res["doc_id"] == doc_id
            assert op2_res["seq"] == 3


class TestReplayEvent:
    @pytest.mark.anyio
    async def test_replay_event(
        self,
        login: tuple[httpx.Response],
        websocket_client: httpx.AsyncClient,
        create_document: httpx.Response,
    ):
        doc_id = create_document.json()["data"]["id"]

        login_res_1, login_res_2 = login
        access_token_1 = login_res_1.json()["data"]["access_token"]
        access_token_2 = login_res_2.json()["data"]["access_token"]

        async with (
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_1}", client=websocket_client
            ) as client1,
            aconnect_ws(
                url=f"{WEBSOCKET_URL}?token={access_token_2}", client=websocket_client
            ) as client2,
        ):
            # simulate connection loss and replay when reconnected
            join_payload: dict = {"type": "join", "doc_id": doc_id}
            replay_payload: dict = {"type": "replay", "doc_id": doc_id, "seq": 1}

            operation: dict = {"kind": "insert", "pos": 0, "text": "hello "}
            operation_payload: dict = {
                "type": "operation",
                "doc_id": doc_id,
                "op": operation,
                "base_seq": 1,
            }

            await client2.send_json(join_payload)
            await client2.send_json(operation_payload)

            try:
                # receive joined and presence responses
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)
                await client2.receive_json(timeout=TIMEOUT)

                # rejoin room
                await client1.send_json(join_payload)

                # receive joined and presence responses
                await client1.receive_json(timeout=TIMEOUT)
                await client1.receive_json(timeout=TIMEOUT)

                await client1.send_json(replay_payload)
                res = await client1.receive_json(timeout=TIMEOUT)
            except TimeoutError:
                print("No data received!!!!")

            assert res["type"] == "operation"
            assert res["doc_id"] == doc_id
            assert res["seq"] == 2
