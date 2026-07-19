from enum import Enum
from pydantic import BaseModel, ConfigDict


class EventType(str, Enum):
    ACK = "ack"
    PING = "ping"
    PONG = "pong"
    JOIN = "join"
    LEAVE = "leave"
    ERROR = "error"
    JOINED = "joined"
    CURSOR = "cursor"
    TYPING = "typing"
    REPLAY = "replay"
    PRESENCE = "presence"
    OPERATION = "operation"
    USER_LEFT = "user_left"
    USER_JOINED = "user_joined"


class OperationKind(str, Enum):
    INSERT = "insert"
    DELETE = "delete"


class TypingMode(str, Enum):
    STARTED = "started"
    STOPPED = "stopped"


class EventBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    doc_id: str


class Operation(BaseModel):
    kind: OperationKind
    pos: int
    text: str


# Client → Server
class JoinEvent(EventBase):
    type: EventType = EventType.JOIN


class LeaveEvent(EventBase):
    type: EventType = EventType.LEAVE


class OperationEvent(EventBase):
    type: EventType = EventType.OPERATION
    op: Operation
    base_seq: int


class CursorEvent(EventBase):
    type: EventType = EventType.CURSOR
    pos: int


class TypingEvent(EventBase):
    type: EventType = EventType.TYPING


class ReplayEvent(EventBase):
    type: EventType = EventType.REPLAY
    seq: int


class PingEvent(EventBase):
    type: EventType = EventType.PING

# Server → Client
class UserIdResponse(EventBase):
    user_id: str

class JoinedResponse(EventBase):
    type: EventType = EventType.JOINED
    content: str
    seq: int


class AckResponse(EventBase):
    type: EventType = EventType.ACK
    seq: int


class OperationResponse(UserIdResponse):
    type: EventType = EventType.OPERATION
    op: Operation
    seq: int


class CursorResponse(UserIdResponse):
    type: EventType = EventType.CURSOR
    pos: int


class TypingResponse(UserIdResponse):
    type: EventType = EventType.TYPING
    mode: TypingMode


class UserJoinedResponse(UserIdResponse):
    type: EventType = EventType.USER_JOINED
    display_name: str


class LeftResponse(UserIdResponse):
    type: EventType = EventType.USER_LEFT


class PresenceResponse(EventBase):
    type: EventType = EventType.PRESENCE
    users: list[str]


class PongResponse(BaseModel):
    type: EventType = EventType.PONG
