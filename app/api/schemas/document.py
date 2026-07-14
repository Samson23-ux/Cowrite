from uuid import UUID, uuid7
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


from app.api.models.document import DocumentRoleEnum


class DocumentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=8)
    content: str = Field(..., min_length=50)


class DocumentInDb(DocumentBase):
    id: UUID = uuid7()
    created_by: UUID


class DocumentCreate(DocumentBase):
    pass


class DocumentMember(BaseModel):
    doc_id: UUID
    user_id: UUID
    role: DocumentRoleEnum


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content: str
    sequence: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
