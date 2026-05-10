

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class DocumentTypeDefinition(Base):
    """Admin-configurable catalogue of document types."""

    __tablename__ = "document_type_definitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_by_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    requirements: Mapped[list["ApplicationDocumentRequirement"]] = relationship(
        back_populates="document_type"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="document_type")

    __table_args__ = (
        Index("ix_doc_type_defs_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentTypeDefinition id={self.id} "
            f"name={self.name!r} "
            f"required={self.is_required}>"
        )

class ApplicationDocumentRequirement(Base):
    """Snapshot of required documents for a specific application."""

    __tablename__ = "application_document_requirements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document_type_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_satisfied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    application: Mapped["Application"] = relationship(
        back_populates="document_requirements"
    )
    document_type: Mapped[DocumentTypeDefinition] = relationship(
        back_populates="requirements"
    )

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "document_type_id",
            name="uq_app_doc_requirement",
        ),
        Index("ix_app_doc_req_application_id", "application_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationDocumentRequirement "
            f"app={self.application_id} "
            f"type={self.document_type_id} "
            f"satisfied={self.is_satisfied}>"
        )

class Document(Base):
    """Metadata for a single file upload."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("document_type_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    upload_round: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="initial",
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    application: Mapped["Application"] = relationship(back_populates="documents")
    document_type: Mapped[Optional[DocumentTypeDefinition]] = relationship(
        back_populates="documents"
    )
    uploader: Mapped["User"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes <= 5242880",
            name="ck_documents_max_5mb",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_documents_positive_size",
        ),
        Index(
            "ix_documents_app_type_version",
            "application_id",
            "document_type_id",
            "version_number",
        ),
        Index(
            "ix_documents_app_type_latest",
            "application_id",
            "document_type_id",
            "is_latest",
        ),
        Index("ix_documents_application_id", "application_id"),
        Index("ix_documents_uploaded_by", "uploaded_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} "
            f"filename={self.original_filename!r} "
            f"v{self.version_number} "
            f"latest={self.is_latest}>"
        )
