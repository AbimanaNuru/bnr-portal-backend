from datetime import datetime
from uuid import uuid4
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Table, Column, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
from app.db.base import Base

# Junction tables
user_role = Table("user_role", Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

role_permission = Table("role_permission", Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

class PermissionCategory(Base):
    """
    Groups permissions into logical categories (e.g. 'Property Management', 'User Management').
    """
    __tablename__ = "permission_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    fullname: Mapped[str] = mapped_column(String(200), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())

    # Advanced Auth Fields
    is_two_factor_auth: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # BNR Specific Fields
    institution_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_role, back_populates="users", lazy="selectin")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)   # e.g. APPLICANT, REVIEWER, APPROVER, ADMIN
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list[User]] = relationship("User", secondary=user_role, back_populates="roles", lazy="selectin")
    permissions: Mapped[list["Permission"]] = relationship("Permission", secondary=role_permission, back_populates="roles", lazy="selectin")

class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)   # e.g. application:submit, application:review, application:approve
    resource: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("permission_categories.id", ondelete="SET NULL"), nullable=True)

    category: Mapped[PermissionCategory | None] = relationship("PermissionCategory", back_populates="permissions")
    roles: Mapped[list[Role]] = relationship("Role", secondary=role_permission, back_populates="permissions")

