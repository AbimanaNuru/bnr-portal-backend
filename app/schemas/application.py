from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID

from app.models.application import ApplicationStatus, InstitutionType

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
    
    # Section 1: Institution Identity
    institution_name: str = Field(..., max_length=512)
    institution_type: InstitutionType
    registration_number: str = Field(..., max_length=100)

    # Section 2: Contact Person
    contact_full_name: str = Field(..., max_length=255)
    contact_title: str = Field(..., max_length=100)
    contact_email: str = Field(..., max_length=255)
    contact_phone: str = Field(..., max_length=30)

    # Section 3: Proposed Operations
    proposed_capital: str = Field(..., max_length=50)
    primary_products: str
    target_districts: str = Field(..., max_length=512)

    # Section 4: Declaration & Notes
    declaration_accepted: bool = False
    additional_notes: Optional[str] = None
    
    extra_metadata: Optional[Dict[str, Any]] = None

class ApplicationCreate(ApplicationBase):
    """Used when applicant creates a new application"""
    workflow_id: Optional[str] = None

class ApplicationUpdate(ApplicationBase):
    """Used for updates (especially when information is requested)"""
    version: int

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
    version: int
    
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    reviewer_notes: Optional[str] = None
    
    declaration_accepted_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    applicant: Optional[UserRead] = None
    approvals: list[ApplicationApprovalRead] = []

    class Config:
        from_attributes = True

class StateTransitionRequest(BaseModel):
    """Request body for changing application state"""
    action: str = Field(..., description="e.g. submit, approve, reject, request_information")
    notes: Optional[str] = Field(None, max_length=1000)
    version: int

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
