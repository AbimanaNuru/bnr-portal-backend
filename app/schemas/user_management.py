from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field

class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None

class PermissionRead(PermissionBase):
    id: UUID

    class Config:
        from_attributes = True

class PermissionCategoryRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    permissions: List[PermissionRead] = []

    class Config:
        from_attributes = True

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleRead(RoleBase):
    id: UUID
    permissions: List[PermissionRead] = []

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr
    fullname: str
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True

class UserRead(UserBase):
    id: UUID
    email_verified: bool = False
    deleted_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserWithRoles(UserRead):
    roles: List[RoleRead] = []

class UserUpdate(BaseModel):
    fullname: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None

class UserStatusUpdate(BaseModel):
    is_active: bool

class UserListResponse(BaseModel):
    success: bool = True
    data: List[UserRead]
    total: int
    page: int
    page_size: int
    total_pages: int

class UserMeProfile(BaseModel):
    id: UUID
    fullname: str
    email: EmailStr
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    email_verified: bool
    last_login_at: Optional[datetime] = None
    is_two_factor_auth: bool
    permissions: List[str] = []

class GlobalAccess(BaseModel):
    permissions: List[str]

class PropertyContext(BaseModel):
    id: str
    name: str

class SubscriptionContext(BaseModel):
    plan: str
    status: str
    expires_at: datetime
    features: List[str]
    limits: dict = {
        "units": {"max": 0, "used": 0},
        "users": {"max": 0, "used": 0}
    }

class ContextItem(BaseModel):
    property: PropertyContext
    access: GlobalAccess
    subscription: SubscriptionContext

class UserMeResponse(BaseModel):
    user: UserMeProfile


    class Config:
        allow_population_by_field_name = True

class RoleAssignRequest(BaseModel):
    role_id: UUID

class PermissionAssignRequest(BaseModel):
    permission_id: UUID
