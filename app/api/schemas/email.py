from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr


class EmailBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class EmailInDB(EmailBase):
    id: UUID
    processed_email: EmailStr
