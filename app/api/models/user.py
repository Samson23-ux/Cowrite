import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    Boolean,
    text,
    UUID,
    DateTime,
    PrimaryKeyConstraint,
    Index,
    Enum,
)

from app.api.models.base import Base


class UserType(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    type: Mapped[UserType] = mapped_column(
        Enum(UserType, values_callable=lambda e: [m.value for m in e])
    )
    email: Mapped[str | None] = mapped_column(String, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String)
    google_id: Mapped[str | None] = mapped_column(String)
    google_email: Mapped[str | None] = mapped_column(String, unique=True)
    display_name: Mapped[str | None] = mapped_column(String, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="users_pk"),
        Index("idx_users_email", email),
        Index("idx_users_google_id", google_id),
    )
