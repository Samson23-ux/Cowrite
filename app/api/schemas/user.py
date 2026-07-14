from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict

from app.api.models.user import UserType


class UserBase(BaseModel):
    type: UserType
    display_name: str
    is_active: bool = False
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class GoogleUser(UserBase):
    google_id: Optional[str] = None
    google_email: Optional[EmailStr] = None


class EmailUser(UserBase):
    email: Optional[EmailStr] = None


class UserInDB(GoogleUser, EmailUser):
    hashed_password: Optional[str] = None


class GoogleUserResponse(GoogleUser):
    id: UUID


class EmailUserResponse(EmailUser):
    id: UUID
