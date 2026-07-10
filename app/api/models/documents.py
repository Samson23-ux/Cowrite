import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    UUID,
    Enum,
    text,
    Index,
    String,
    Integer,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
)

from app.api.models.base import Base


class DocumentRoleEnum(str, enum.Enum):
    AUTHOR = "author"
    EDITOR = "editor"
    VIEWER = "viewer"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", name="documents_created_by_fk", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (PrimaryKeyConstraint("id", name="documents_pk"),)


class DocumentMember(Base):
    """all memebrs present in a document room"""
    __tablename__ = "document_members"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "documents.id", name="members_document_id_by_fk", ondelete="CASCADE"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", name="members_user_id_by_fk", ondelete="CASCADE")
    )
    role: Mapped[enum.Enum] = mapped_column(
        Enum(DocumentRoleEnum, values_callable=lambda e: [m.value for m in e])
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        PrimaryKeyConstraint("document_id", "user_id", name="document_members_pk"),
        Index("idx_document_members", document_id, user_id)
    )
