from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    JSON, DateTime, ForeignKey, Index, Integer, String, Text,
    Boolean, CheckConstraint
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.user import User

if TYPE_CHECKING:
    from app.models.approval_workflow import ApplicationApproval, ApprovalWorkflow
    from app.models.documents import Document, ApplicationDocumentRequirement

class ApplicationStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    INFORMATION_REQUESTED = "INFORMATION_REQUESTED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class InstitutionType(str, Enum):
    COMMERCIAL_BANK = "COMMERCIAL_BANK"
    MICROFINANCE = "MICROFINANCE"
    FOREX_BUREAU = "FOREX_BUREAU"
    PAYMENT_PROVIDER = "PAYMENT_PROVIDER"

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Applicant info
    applicant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    applicant: Mapped["User"] = relationship(
        "User", foreign_keys=[applicant_id], lazy="selectin"
    )

    # Workflow & Tracking
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("approval_workflows.id"), nullable=False
    )
    workflow: Mapped["ApprovalWorkflow"] = relationship("ApprovalWorkflow")

    current_level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus, native_enum=False), default=ApplicationStatus.DRAFT, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Reviewer/Approver (Staff)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Institution Identity
    institution_name: Mapped[str] = mapped_column(String(512), nullable=False)
    institution_type: Mapped[InstitutionType] = mapped_column(
        SQLEnum(InstitutionType), nullable=False
    )
    registration_number: Mapped[str] = mapped_column(String(100), nullable=False)

    # Contact Person
    contact_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_title: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)

    # Proposed Operations
    proposed_capital: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_products: Mapped[str] = mapped_column(Text, nullable=False)
    target_districts: Mapped[str] = mapped_column(String(512), nullable=False)

    # Declaration
    declaration_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    declaration_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    reviewer: Mapped[User | None] = relationship("User", foreign_keys="Application.reviewed_by")
    approver: Mapped[User | None] = relationship("User", foreign_keys="Application.approved_by")

    state_history: Mapped[list["ApplicationStateHistory"]] = relationship(
        "ApplicationStateHistory",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list["ApplicationApproval"]] = relationship(
        "ApplicationApproval",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    document_requirements: Mapped[list["ApplicationDocumentRequirement"]] = relationship(
        "ApplicationDocumentRequirement",
        back_populates="application",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "reviewed_by != approved_by OR reviewed_by IS NULL OR approved_by IS NULL",
            name="ck_reviewer_not_approver",
        ),
        Index("ix_applications_applicant_id", "applicant_id"),
        Index("ix_applications_status", "status"),
    )

    __mapper_args__ = {
        "version_id_col": version
    }

    def __repr__(self) -> str:
        return (
            f"<Application id={self.id} "
            f"institution={self.institution_name!r} "
            f"status={self.status!r}>"
        )

class ApplicationStateHistory(Base):
    __tablename__ = "application_state_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )

    from_status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus, native_enum=False))
    to_status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus, native_enum=False))

    changed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_by: Mapped["User"] = relationship("User", foreign_keys=[changed_by_id])

    # Contextual info for the new architecture
    level_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped[Application] = relationship(
        "Application", back_populates="state_history"
    )

    __table_args__ = (
        Index("ix_app_history_application", "application_id"),
        Index("ix_app_history_changed_by", "changed_by_id"),
    )
