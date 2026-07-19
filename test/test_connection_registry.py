import pytest
from uuid import uuid4
from fastapi import WebSocketDisconnect
from unittest.mock import MagicMock, AsyncMock


from app.api.schemas.websocket import WebSocket as WebSocketSchema
from app.api.services.connection_registry import ConnectionRegistry

CHANNEL = "test:channel"


@pytest.fixture
def connection_registry() -> ConnectionRegistry:
    redis = AsyncMock()
    return ConnectionRegistry(redis_repo=redis)


def mock_websocket() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock()

    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()

    return bus


def get_websocket_schema() -> WebSocketSchema:
    websocket = MagicMock()

    websocket.websocket = mock_websocket()
    websocket.user_id = uuid4()
    websocket.user_email = "user@example.com"

    return websocket


class TestConnect:
    @pytest.mark.anyio
    async def test_single_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws, mock_event_bus, CHANNEL)

        assert connection_registry.get_room_connections(doc_id) == 1
        assert ws in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_multiple_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        await connection_registry.connect(doc_id, ws2, mock_event_bus, CHANNEL)

        assert connection_registry.get_room_connections(doc_id) == 2

        assert ws1 in connection_registry.get_connections(doc_id)
        assert ws2 in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_single_connection_multiple_docs(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        ws1 = get_websocket_schema()

        await connection_registry.connect(
            doc_id1, ws1, mock_event_bus, CHANNEL
        )
        await connection_registry.connect(
            doc_id2, ws1, mock_event_bus, CHANNEL
        )

        assert connection_registry.get_room_connections(doc_id1) == 1
        assert connection_registry.get_room_connections(doc_id2) == 1

        assert ws1 in connection_registry.get_connections(doc_id1)
        assert ws1 in connection_registry.get_connections(doc_id2)

    @pytest.mark.anyio
    async def test_multiple_connection_multiple_docs(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(
            doc_id1, ws1, mock_event_bus, CHANNEL
        )
        await connection_registry.connect(
            doc_id2, ws2, mock_event_bus, CHANNEL
        )

        assert connection_registry.get_room_connections(doc_id1) == 1
        assert connection_registry.get_room_connections(doc_id2) == 1

        assert ws1 in connection_registry.get_connections(doc_id1)
        assert ws2 in connection_registry.get_connections(doc_id2)


class TestDisconnect:
    @pytest.mark.anyio
    async def test_disconnect_single_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws, mock_event_bus, CHANNEL)
        await connection_registry.disconnect(doc_id, ws, mock_event_bus, CHANNEL)

        assert connection_registry.get_room_connections(doc_id) == 0
        assert ws not in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_disconnect_multiple_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        await connection_registry.connect(doc_id, ws2, mock_event_bus, CHANNEL)

        await connection_registry.disconnect(doc_id, ws1, mock_event_bus, CHANNEL)

        assert connection_registry.get_room_connections(doc_id) == 1

        assert ws1 not in connection_registry.get_connections(doc_id)
        assert ws2 in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_disconnect_no_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws = get_websocket_schema()

        await connection_registry.disconnect(doc_id, ws, mock_event_bus, CHANNEL)
        assert doc_id not in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_last_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws, mock_event_bus, CHANNEL)
        await connection_registry.disconnect(doc_id, ws, mock_event_bus, CHANNEL)

        assert doc_id not in connection_registry.get_connections(doc_id)


class TestBroadcast:
    @pytest.mark.anyio
    async def test_broadcast(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        data = {"data": "test"}
        ws = get_websocket_schema()

        await connection_registry.connect(doc_id, ws, mock_event_bus, CHANNEL)
        await connection_registry.broadcast(data, doc_id, ws)

        ws.websocket.send_json.assert_awaited_once_with(data)

    @pytest.mark.anyio
    async def test_broadcast_single_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        data = {"data": "test"}

        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        await connection_registry.connect(doc_id, ws2, mock_event_bus, CHANNEL)

        await connection_registry.broadcast(data, doc_id, ws1)
        ws1.websocket.send_json.assert_awaited_once_with(data)
        ws2.websocket.send_json.assert_not_awaited()

    @pytest.mark.anyio
    async def test_broadcast_closed_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        data = {"data": "test"}
        ws = get_websocket_schema()

        ws.websocket.send_json.side_effects = WebSocketDisconnect(
            reason="Connection closed"
        )

        await connection_registry.broadcast(data, doc_id, ws)

        assert ws not in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_broadcast_no_connection(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws = get_websocket_schema()

        await connection_registry.disconnect(doc_id, ws, mock_event_bus, CHANNEL)
        assert doc_id not in connection_registry.get_connections(doc_id)


class TestRoomConnectionsMetrics:
    @pytest.mark.anyio
    async def test_get_connections_number(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        await connection_registry.connect(doc_id, ws2, mock_event_bus, CHANNEL)
        assert connection_registry.get_room_connections(doc_id) == 2

    @pytest.mark.anyio
    async def test_no_connections(self, connection_registry: ConnectionRegistry):
        doc_id = str(uuid4())
        assert connection_registry.get_room_connections(doc_id) == 0


class TestConnections:
    @pytest.mark.anyio
    async def test_get_connections(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()
        ws2 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        await connection_registry.connect(doc_id, ws2, mock_event_bus, CHANNEL)

        assert ws1 in connection_registry.get_connections(doc_id)
        assert ws2 in connection_registry.get_connections(doc_id)

    @pytest.mark.anyio
    async def test_no_connections(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()

        assert ws1 not in connection_registry.get_connections(doc_id)


class TestConnectivity:
    @pytest.mark.anyio
    async def test_get_connectivity(
        self, connection_registry: ConnectionRegistry, mock_event_bus: MagicMock
    ):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()

        await connection_registry.connect(doc_id, ws1, mock_event_bus, CHANNEL)
        assert connection_registry.check_connectivity(doc_id, ws1) is True

    @pytest.mark.anyio
    async def test_no_connectivity(self, connection_registry: ConnectionRegistry):
        doc_id = str(uuid4())
        ws1 = get_websocket_schema()

        assert connection_registry.check_connectivity(doc_id, ws1) is False
