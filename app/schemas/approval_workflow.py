from datetime import datetime
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel

class RoleReadBasic(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True

class ApprovalLevelBase(BaseModel):
    level_number: int
    name: str
    required_approvals: int = 1

class ApprovalLevelCreate(ApprovalLevelBase):
    role_ids: List[UUID] = []

class ApprovalLevelUpdate(BaseModel):
    level_number: Optional[int] = None
    name: Optional[str] = None
    required_approvals: Optional[int] = None
    role_ids: Optional[List[UUID]] = None

class ApprovalLevelRead(ApprovalLevelBase):
    id: UUID
    workflow_id: UUID
    roles: List[RoleReadBasic] = []

    class Config:
        from_attributes = True

class ApprovalWorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class ApprovalWorkflowCreate(ApprovalWorkflowBase):
    levels: List[ApprovalLevelCreate] = []

class ApprovalWorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ApprovalWorkflowRead(ApprovalWorkflowBase):
    id: UUID
    created_at: datetime
    levels: List[ApprovalLevelRead] = []

    class Config:
        from_attributes = True

class RoleAssignRequest(BaseModel):
    role_id: UUID
