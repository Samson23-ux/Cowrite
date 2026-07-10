import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    text,
    Enum,
    UUID,
    Index,
    String,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
)

from app.api.models.base import Base


class OtpStatus(str, enum.Enum):
    VALID = "valid"
    USED = "used"


class Otp(Base):
    __tablename__ = "otp"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    otp: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", name="otp_user_id_fk", ondelete="CASCADE")
    )
    status: Mapped[OtpStatus] = mapped_column(
        Enum(OtpStatus, values_callable=lambda e: [m.value for m in e])
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_auth_otp", otp),
        PrimaryKeyConstraint("id", name="otp_id_pk"),
    )
