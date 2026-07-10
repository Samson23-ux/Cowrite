from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=8)
    content: str = Field(..., min_length=50)


class DocumentInDb(DocumentBase):
    sequence: int
    created_by: UUID


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content: str
    sequence: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
