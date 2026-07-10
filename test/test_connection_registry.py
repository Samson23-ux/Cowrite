import pytest
from uuid import uuid4
from fastapi import WebSocketDisconnect
from unittest.mock import MagicMock, AsyncMock


from app.api.schemas.websocket import WebSocket as WebSocketSchema
from app.api.services.connection_registry import ConnectionRegistry


@pytest.fixture
def connection_registry() -> ConnectionRegistry:
    return ConnectionRegistry()


def mock_websocket() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


def get_websocket_schema() -> WebSocketSchema:
    return WebSocketSchema(
        websocket=mock_websocket(), user_id=uuid4(), user_email="user@example.com"
    )


class TestConnect:
    @pytest.mark.asyncio
    async def test_single_connection(self, connection_registry: ConnectionRegistry):
        doc_id = uuid4()
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws)

        assert await connection_registry.get_room_connections(doc_id) == 1
        assert ws in connection_registry.active_connections[doc_id]

    @pytest.mark.asyncio
    async def test_multiple_connection(self, connection_registry: ConnectionRegistry):
        doc_id = uuid4()
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1)
        await connection_registry.connect(doc_id, ws2)

        assert await connection_registry.get_room_connections(doc_id) == 2

        assert ws1 in connection_registry.active_connections[doc_id]
        assert ws2 in connection_registry.active_connections[doc_id]

    @pytest.mark.asyncio
    async def test_single_connection_multiple_docs(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        ws1 = get_websocket_schema()

        await connection_registry.connect(doc_id1, ws1)
        await connection_registry.connect(doc_id2, ws1)

        assert await connection_registry.get_room_connections(doc_id1) == 1
        assert await connection_registry.get_room_connections(doc_id2) == 1

        assert ws1 in connection_registry.active_connections[doc_id1]
        assert ws1 in connection_registry.active_connections[doc_id2]

    @pytest.mark.asyncio
    async def test_multiple_connection_multiple_docs(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id1, ws1)
        await connection_registry.connect(doc_id2, ws2)

        assert await connection_registry.get_room_connections(doc_id1) == 1
        assert await connection_registry.get_room_connections(doc_id2) == 1

        assert ws1 in connection_registry.active_connections[doc_id1]
        assert ws2 in connection_registry.active_connections[doc_id2]


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_single_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws)
        await connection_registry.disconnect(doc_id, ws)

        assert await connection_registry.get_room_connections(doc_id) == 0
        assert ws not in connection_registry.active_connections[doc_id]

    @pytest.mark.asyncio
    async def test_disconnect_multiple_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1)
        await connection_registry.connect(doc_id, ws2)

        await connection_registry.disconnect(doc_id, ws1)

        assert await connection_registry.get_room_connections(doc_id) == 1

        assert ws1 not in connection_registry.active_connections[doc_id]
        assert ws2 in connection_registry.active_connections[doc_id]

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        ws = get_websocket_schema()

        await connection_registry.disconnect(doc_id, ws)
        assert doc_id not in connection_registry.active_connections

    @pytest.mark.asyncio
    async def test_last_connection(self, connection_registry: ConnectionRegistry):
        doc_id = uuid4()
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws)
        await connection_registry.disconnect(doc_id, ws)

        assert doc_id not in connection_registry.active_connections


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast(self, connection_registry: ConnectionRegistry):
        doc_id = uuid4()
        data = {"data": "test"}
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws)
        await connection_registry.broadcast(doc_id, ws, data)

        assert ws.websocket.send_json.assert_awaited_once_with(data)

    @pytest.mark.asyncio
    async def test_broadcast_single_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        data = {"data": "test"}

        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1)
        await connection_registry.connect(doc_id, ws2)

        await connection_registry.broadcast(doc_id, ws1, data)
        assert ws1.websocket.send_json.assert_awaited_once_with(data)
        assert ws2.websocket.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_closed_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        data = {"data": "test"}
        ws = get_websocket_schema()

        ws.websocket.send_json.side_effects = WebSocketDisconnect(
            reason="Connection closed"
        )

        await connection_registry.connect(doc_id, ws)
        await connection_registry.broadcast(doc_id, ws, data)

        assert ws not in connection_registry.active_connections[doc_id]

    @pytest.mark.asyncio
    async def test_broadcast_no_connection(
        self, connection_registry: ConnectionRegistry
    ):
        doc_id = uuid4()
        ws = get_websocket_schema()

        await connection_registry.disconnect(doc_id, ws)
        assert doc_id not in connection_registry.active_connections


class TestRoomConnectionsMetrics:
    @pytest.mark.asyncio
    async def test_get_connections(self, connection_registry: ConnectionRegistry):
        doc_id = uuid4()
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1)
        await connection_registry.connect(doc_id, ws2)
        assert await connection_registry.get_room_connections(doc_id) == 2
