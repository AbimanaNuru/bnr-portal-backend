from __future__ import annotations
from sqlalchemy import String, ForeignKey, Boolean, Text, Integer, Table, Column, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from uuid import uuid4
from typing import TYPE_CHECKING

from app.db.base import Base
from app.models.user import Role, User

if TYPE_CHECKING:
    from app.models.application import Application


# Many-to-Many: Level <-> Roles (who can approve at this level)
level_role = Table(
    "approval_level_role", Base.metadata,
    Column("level_id", String(36), ForeignKey("approval_levels.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)   # e.g. "Loan Approval", "System Change Request"
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    levels: Mapped[list["ApprovalLevel"]] = relationship(
        "ApprovalLevel", back_populates="workflow", cascade="all, delete-orphan",
        order_by="ApprovalLevel.level_number"
    )


class ApprovalLevel(Base):
    __tablename__ = "approval_levels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("approval_workflows.id", ondelete="CASCADE"))
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)   # 1, 2, 3...
    name: Mapped[str] = mapped_column(String(100))                       # e.g. "Line Manager Review", "Risk & Compliance"

    # How many approvals needed at this level (1 = single, 2 = two people must approve, etc.)
    required_approvals: Mapped[int] = mapped_column(Integer, default=1)

    workflow: Mapped[ApprovalWorkflow] = relationship("ApprovalWorkflow", back_populates="levels")
    
    # Who can approve at this level
    roles: Mapped[list[Role]] = relationship("Role", secondary=level_role)

    __table_args__ = (
        Index("ix_approval_level_workflow", "workflow_id", "level_number", unique=True),
    )


class ApplicationApproval(Base):
    """Tracks who approved what and at which level"""
    __tablename__ = "application_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    level_id: Mapped[str] = mapped_column(ForeignKey("approval_levels.id"))
    approved_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    
    approved_at: Mapped[datetime] = mapped_column(server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)

    application: Mapped[Application] = relationship("Application", back_populates="approvals")
    approved_by: Mapped[User] = relationship("User")
    level: Mapped[ApprovalLevel] = relationship(ApprovalLevel)
