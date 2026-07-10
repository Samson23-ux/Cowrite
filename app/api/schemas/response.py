from pydantic import BaseModel
from typing import TypeVar, Generic, Optional

T = TypeVar("T", bound=BaseModel)


class SuccessResponse(BaseModel, Generic[T]):
    status: str = "success"
    message: Optional[str] = None
    data: Optional[T | list[T]] = None


class AllSuccessResponse(SuccessResponse):
    cursor: str | None
