from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from app.db.session import get_db
from app.core.security.dependencies import get_current_active_user, require_permission
from app.core.security.permissions import Permission
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.audit_service import audit
from app.schemas.auth import (
    ApplicantRegisterRequest,
    StaffCreateRequest,
    LoginRequest,
    TokenResponse,
    RegisterResponse,
    ChangePasswordRequest,
    UserBasicInfoUpdate,
    RefreshToken
)
from app.core.security.security import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as an applicant institution representative",
)
@audit(action="USER_REGISTER", resource="user")
def register_applicant(
    payload: ApplicantRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public registration for applicants only.
    Role is always set to APPLICANT.
    """
    return AuthService(db).register_applicant(payload)

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in — any role",
)
@audit(action="USER_LOGIN", resource="user")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    return AuthService(db).login(payload)

@router.post(
    "/staff",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: provision a staff account (reviewer / approver / admin)",
    dependencies=[Depends(require_permission(Permission.USERS_CREATE))]
)
@audit(action="STAFF_PROVISION", resource="user")
def create_staff_account(
    payload: StaffCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_CREATE))
):
    """
    Admin-only. Creates reviewer, approver, or admin accounts.
    """
    return AuthService(db).create_staff(payload)

@router.post(
    "/change-password",
    summary="Change own password",
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return AuthService(db).change_password(current_user, payload)

@router.patch(
    "/update-profile",
    summary="Update own profile basic info",
)
def update_profile(
    payload: UserBasicInfoUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_service = UserService(db)
    # We'll adapt update_me or similar if it exists, otherwise implement here
    if payload.fullname:
        current_user.fullname = payload.fullname
    if payload.phone_number:
        current_user.phone_number = payload.phone_number
    if payload.avatar_url:
        current_user.avatar_url = payload.avatar_url

    db.commit()
    return {"detail": "Profile updated successfully"}

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshToken,
    db: Session = Depends(get_db)
):
    # Basic refresh logic - in production use a more robust version with JWT decoding
    # For now, keeping it simple as it was in the original code
    from jose import jwt, JWTError
    from app.core.security.security import SECRET_KEY, ALGORITHM

    try:
        payload_data = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload_data.get("type") != "refresh":
            raise HTTPException(status_code=403, detail="Invalid token type")

        user_id = payload_data.get("sub")
        db_user: User | None = db.query(User).filter(User.id == user_id).first()

        if not db_user or not db_user.is_active:
            raise HTTPException(status_code=403, detail="User not found or inactive")

        token_data = {
            "sub": str(db_user.id),
            "email": db_user.email,
            "role": db_user.roles[0].name if db_user.roles else "USER"
        }

        return TokenResponse(
            access_token=create_access_token(data=token_data),
            refresh_token=payload.refresh_token,
            role=token_data["role"],
            user_id=UUID(str(db_user.id)),
            full_name=str(db_user.fullname),
            must_change_password=bool(db_user.must_change_password)
        )
    except JWTError:
        raise HTTPException(status_code=403, detail="Could not validate refresh token")
