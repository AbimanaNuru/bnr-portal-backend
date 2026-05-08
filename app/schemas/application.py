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

    model_config = ConfigDict(from_attributes=True)


class ApplicationBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    extra_metadata: Optional[Dict[str, Any]] = None


class ApplicationCreate(ApplicationBase):
    """Used when applicant creates a new application"""
    pass


class ApplicationUpdate(ApplicationBase):
    """Used for updates (especially when information is requested)"""
    pass


class ApplicationRead(ApplicationBase):
    id: str
    applicant_id: str
    status: ApplicationStatus
    reviewer_id: Optional[str] = None
    decision_maker_id: Optional[str] = None
    
    applicant: Optional[UserRead] = None
    reviewer: Optional[UserRead] = None
    decision_maker: Optional[UserRead] = None
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StateTransitionRequest(BaseModel):
    """Request body for changing application state"""
    action: str = Field(..., description="e.g. submit, start_review, request_information, complete_review, approve, reject")
    notes: Optional[str] = Field(None, max_length=1000)
    reviewer_id: Optional[str] = None   # Only needed for start_review


class ApplicationStateHistoryRead(BaseModel):
    id: str
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    changed_by: UserRead
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
