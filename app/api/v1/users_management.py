from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import math

from app.db.session import get_db
from app.models.user import User
from app.core.security.dependencies import get_current_active_user, require_permission
from app.services.user_service import UserService
from app.schemas.user_management import (
    UserRead,
    UserWithRoles,
    UserListResponse,
    UserMeResponse,
    UserStatusUpdate,
    RoleRead,
    PermissionRead,
    PermissionCategoryRead,
    RoleAssignRequest,
    PermissionAssignRequest
)

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user profile with detailed context
    """
    # Extract global roles and permissions
    global_roles = [role.name for role in current_user.roles]
    global_perms = set()
    for role in current_user.roles:
        for perm in role.permissions:
            global_perms.add(perm.name)

    return {
        "user": {
            "id": current_user.id,
            "fullname": current_user.fullname,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "avatar_url": current_user.avatar_url,
            "is_active": current_user.is_active,
            "email_verified": current_user.email_verified,
            "last_login_at": current_user.last_login_at,
            "is_two_factor_auth": current_user.is_two_factor_auth
        },
        "global_": {
            "roles": list(global_roles),
            "permissions": list(global_perms)
        },
        "contexts": [],
        "current_context": None
    }


# Roles & Permissions
@router.get("/permissions", response_model=List[PermissionRead])
async def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    return service.list_permissions()

@router.get("/permission-categories", response_model=List[PermissionCategoryRead])
async def list_permission_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    return service.list_permission_categories()

@router.get("/roles", response_model=List[RoleRead])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    return service.list_roles()

@router.post("/roles/{role_id}/permissions")
async def assign_permission_to_role(
    role_id: str,
    payload: PermissionAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if service.assign_permission_to_role(role_id, str(payload.permission_id)):
        return "Permission assigned successfully"
    raise HTTPException(status_code=404, detail="Role or Permission not found")

@router.delete("/roles/{role_id}/permissions")
async def remove_permission_from_role(
    role_id: str,
    payload: PermissionAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if service.remove_permission_from_role(role_id, str(payload.permission_id)):
        return "Permission removed successfully"
    raise HTTPException(status_code=404, detail="Role or Permission not found")
#  User Administration
@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    user_role: Optional[str] = None,
    user_status: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    users, total = service.get_users_paginated(page, page_size, search, user_role, user_status)

    return {
        "success": True,
        "data": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0
    }

@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if not service.soft_delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return None

@router.patch("/{user_id}/status")
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if service.update_user_status(user_id, payload):
        return "User status updated successfully"
    raise HTTPException(status_code=404, detail="User not found")

@router.get("/{user_id}/roles", response_model=List[RoleRead])
async def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "read"))
):
    service = UserService(db)
    return service.get_user_roles(user_id)

@router.post("/{user_id}/roles")
async def assign_role_to_user(
    user_id: str,
    payload: RoleAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if service.assign_role_to_user(user_id, str(payload.role_id)):
        return "Role assigned successfully"
    raise HTTPException(status_code=404, detail="User or Role not found")

@router.delete("/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users", "manage"))
):
    service = UserService(db)
    if service.remove_role_from_user(user_id, role_id):
        return "Role removed successfully"
    raise HTTPException(status_code=404, detail="User or Role not found")
