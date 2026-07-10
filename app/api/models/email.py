import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, PrimaryKeyConstraint, UUID, String, Enum

from app.api.models.base import Base


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID)
    processed_email: Mapped[str] = mapped_column(String)
    status: Mapped[enum.Enum] = mapped_column(
        Enum(EmailStatus, values_callable=lambda e: [m.value for m in e]),
        default=EmailStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (PrimaryKeyConstraint("id", name="emails_pk"),)
