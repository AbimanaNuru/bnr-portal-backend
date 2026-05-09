from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID

from app.models import ApplicationStatus


class UserRead(BaseModel):
    id: str
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class ApplicationBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    extra_metadata: Optional[Dict[str, Any]] = None


class ApplicationCreate(ApplicationBase):
    """Used when applicant creates a new application"""
    workflow_id: str


class ApplicationUpdate(ApplicationBase):
    """Used for updates (especially when information is requested)"""
    pass


class ApprovalLevelRead(BaseModel):
    id: str
    level_number: int
    name: str
    required_approvals: int

    class Config:
        from_attributes = True


class ApplicationApprovalRead(BaseModel):
    id: str
    level_id: str
    approved_by: UserRead
    approved_at: datetime
    notes: Optional[str] = None
    is_approved: bool

    class Config:
        from_attributes = True


class ApplicationRead(ApplicationBase):
    id: str
    applicant_id: str
    workflow_id: str
    current_level: int
    status: ApplicationStatus

    applicant: Optional[UserRead] = None
    approvals: list[ApplicationApprovalRead] = []

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StateTransitionRequest(BaseModel):
    """Request body for changing application state"""
    action: str = Field(..., description="e.g. submit, approve, reject, request_information")
    notes: Optional[str] = Field(None, max_length=1000)


class ApplicationStateHistoryRead(BaseModel):
    id: str
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    changed_by: UserRead
    level_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
