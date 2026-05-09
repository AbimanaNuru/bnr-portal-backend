
"""
Document handling models.

Three tables, each with a clear job:

  document_type_definitions   — admin-configurable catalogue of what documents exist.
                                Scoped per institution type. Required vs optional.

  application_document_requirements — a snapshot of which document types applied to
                                      THIS application at submission time. Frozen at
                                      submission so future admin changes don't
                                      retroactively affect in-flight applications.

  documents                   — the actual file uploads. Versioned per
                                (application_id, document_type_id). Old versions
                                are never deleted — is_latest flips to False.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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


# ── Document type definitions ─────────────────────────────────────────────────


class DocumentTypeDefinition(Base):
    """
    Admin-configurable catalogue of document types.

    An admin (super admin in your words) creates these entries to define
    what documents each institution type must submit. Applicants see this
    as a checklist when building their application.

    institution_type mirrors the enum on Application so we can filter:
      "show me required docs for a commercial_bank application".
    NULL institution_type means the document applies to ALL institution types.

    is_active = False hides the type from new applications but does not
    affect existing applications that already required it (see the
    application_document_requirements snapshot approach).

    display_order controls the order shown in the UI — admins can
    arrange the checklist to match their internal process.
    """

    __tablename__ = "document_type_definitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        # Shown to applicants so they know exactly what to upload.
        # Write this in plain language, not internal jargon.
    )

    # NULL = applies to all institution types.
    # Non-null = only required for that specific institution type.
    institution_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        # Required = applicant cannot submit without uploading this.
        # Optional = applicant can submit without it but may upload if they have it.
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        # Inactive types are hidden from new applications.
        # Existing requirements referencing this type are unaffected.
    )

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Who created/last modified this definition — for audit purposes.
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

    # Relationships
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    requirements: Mapped[list["ApplicationDocumentRequirement"]] = relationship(
        back_populates="document_type"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="document_type")

    __table_args__ = (
        Index("ix_doc_type_defs_institution_type", "institution_type"),
        Index("ix_doc_type_defs_is_active", "is_active"),
        Index("ix_doc_type_defs_display_order", "display_order"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentTypeDefinition id={self.id} "
            f"name={self.name!r} "
            f"institution_type={self.institution_type!r} "
            f"required={self.is_required}>"
        )


# ── Application document requirements ────────────────────────────────────────


class ApplicationDocumentRequirement(Base):
    """
    Snapshot of required documents for a specific application.

    Created when an application is submitted. Records EXACTLY which
    document types were required at that moment — immune to future
    admin changes to document_type_definitions.

    is_satisfied flips to True when a document of this type is uploaded
    and the application is in a submittable state.

    Why snapshot instead of joining live to document_type_definitions?
    Because if an admin changes a requirement mid-review, we don't want
    to retroactively affect applications already under assessment. The
    snapshot is the contract between BNR and the applicant at submission.
    """

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

    # Snapshot fields — copied from document_type_definitions at submission time.
    # If the definition changes later, these preserve the original contract.
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Satisfied when a document of this type is successfully uploaded.
    is_satisfied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="document_requirements"
    )
    document_type: Mapped[DocumentTypeDefinition] = relationship(
        back_populates="requirements"
    )

    __table_args__ = (
        # One requirement row per document type per application.
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


# ── Documents (actual file uploads) ──────────────────────────────────────────


class Document(Base):
    """
    Metadata for a single file upload.

    File bytes live on disk (simulated local storage).
    Only metadata lives here — name, size, type, path, version.

    Versioning:
      version_number is scoped per (application_id, document_type_id).
      First upload = version 1. Each resubmission increments it.
      is_latest = True on the newest version only. When a new version
      is uploaded, the service sets is_latest = False on all previous
      versions for that (application_id, document_type_id) pair before
      inserting the new record.

      Old versions are NEVER deleted. The requirement says previous
      documents must remain accessible.

    upload_round tracks WHICH submission round this file came from:
      "initial"     — uploaded before first submission
      "resubmit_1"  — uploaded after first INFO_REQUESTED
      "resubmit_2"  — uploaded after second INFO_REQUESTED
      etc.
      This gives reviewers clear context: "this is the document they
      provided after we asked for more information the first time."

    stored_filename is a UUID-based name on disk — never the original
    filename. Prevents path traversal, collisions, and information leakage.
    """

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
        # Nullable: an applicant may upload a supplementary document
        # that doesn't map to any defined type (e.g. a cover letter).
        # Required document types use non-null here.
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # File identity
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)

    # Versioning
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    upload_round: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="initial",
        # Values: "initial", "resubmit_1", "resubmit_2", ...
        # Set by the service layer based on how many times the
        # application has cycled through INFO_REQUESTED.
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    # Relationships
    application: Mapped["Application"] = relationship(back_populates="documents")
    document_type: Mapped[Optional[DocumentTypeDefinition]] = relationship(
        back_populates="documents"
    )
    uploader: Mapped["User"] = relationship()

    __table_args__ = (
        # 5 MB hard limit at the database level — last line of defence.
        # The API layer enforces this first (before writing to disk).
        CheckConstraint(
            "file_size_bytes <= 5242880",
            name="ck_documents_max_5mb",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_documents_positive_size",
        ),
        # Fast lookup of all versions for a given doc type on an application.
        Index(
            "ix_documents_app_type_version",
            "application_id",
            "document_type_id",
            "version_number",
        ),
        # Fast lookup of just the latest version.
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
