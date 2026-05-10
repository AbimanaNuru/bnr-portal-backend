from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStatus, InstitutionType


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ApplicationBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)

    institution_name: str = Field(..., max_length=512)
    institution_type: InstitutionType
    registration_number: str = Field(..., max_length=100)

    contact_full_name: str = Field(..., max_length=255)
    contact_title: str = Field(..., max_length=100)
    contact_email: str = Field(..., max_length=255)
    contact_phone: str = Field(..., max_length=30)

    proposed_capital: str = Field(..., max_length=50)
    primary_products: str
    target_districts: str = Field(..., max_length=512)

    declaration_accepted: bool = False
    additional_notes: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(ApplicationBase):
    version: int


class ApprovalLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    level_number: int
    name: str
    required_approvals: int


class ApplicationApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    level_id: str
    approved_by: UserRead
    approved_at: datetime
    notes: Optional[str] = None
    is_approved: bool


class ApplicationRead(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

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


class StateTransitionRequest(BaseModel):
    action: str = Field(..., description="submit | approve | reject | request_information | resubmit")
    notes: Optional[str] = Field(None, max_length=1000)
    version: int


class ApplicationStateHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    changed_by: UserRead
    level_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
