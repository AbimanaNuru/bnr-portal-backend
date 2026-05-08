from datetime import datetime
from uuid import uuid4
from enum import Enum
from sqlalchemy import String, ForeignKey, Table, Column, Boolean, DateTime, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


# ====================== RBAC MODELS ======================
user_role = Table("user_role", Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permission = Table("role_permission", Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_role, back_populates="users", lazy="selectin")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)   # e.g. APPLICANT, REVIEWER, APPROVER, ADMIN
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list[User]] = relationship("User", secondary=user_role, back_populates="roles", lazy="selectin")
    permissions: Mapped[list["Permission"]] = relationship("Permission", secondary=role_permission, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)   # e.g. application:submit, application:review, application:approve
    resource: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)

    roles: Mapped[list[Role]] = relationship("Role", secondary=role_permission, back_populates="permissions")


# ====================== STATE MACHINE MODELS ======================
class ApplicationStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    INFORMATION_REQUESTED = "INFORMATION_REQUESTED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Applicant info
    applicant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    applicant: Mapped[User] = relationship("User", foreign_keys=[applicant_id], lazy="selectin")

    # Current State
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False
    )

    # Review workflow
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewer_id], lazy="selectin")

    decision_maker_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_maker: Mapped[User | None] = relationship("User", foreign_keys=[decision_maker_id], lazy="selectin")

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    state_history: Mapped[list["ApplicationStateHistory"]] = relationship(
        "ApplicationStateHistory", back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationStateHistory(Base):
    __tablename__ = "application_state_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    
    from_status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus))
    to_status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus))
    
    changed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_by: Mapped[User] = relationship("User", foreign_keys=[changed_by_id])
    
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_maker_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    notes: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship("Application", back_populates="state_history")

    __table_args__ = (
        Index("ix_app_history_application", "application_id"),
        Index("ix_app_history_changed_by", "changed_by_id"),
    )
