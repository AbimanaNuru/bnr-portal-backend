from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status
from uuid import UUID

from app.models.user import User, Role
from app.schemas.auth import (
    ApplicantRegisterRequest,
    StaffCreateRequest,
    TokenResponse,
    RegisterResponse,
    LoginRequest,
    ChangePasswordRequest
)
from app.core.security.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token
)

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def _get_role_by_name(self, name: str) -> Role:
        role = self.db.query(Role).filter(Role.name == name).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Role '{name}' not found in database. Please seed roles."
            )
        return role

    def register_applicant(self, payload: ApplicantRegisterRequest) -> RegisterResponse:
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        applicant_role = self._get_role_by_name("APPLICANT")

        user = User(
            fullname=payload.full_name,
            email=payload.email,
            username=payload.email,  # Using email as username for simplicity
            hashed_password=get_password_hash(payload.password),
            institution_name=payload.institution_name,
            is_active=True,
            must_change_password=False,
        )
        user.roles.append(applicant_role)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return RegisterResponse(
            user_id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(user.fullname),
            role="APPLICANT",
            message="Account created successfully. You can now log in and start your application."
        )

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self.db.query(User).filter(User.email == payload.email).first()

        if not user or not verify_password(payload.password, str(user.hashed_password)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated. Contact BNR administration.",
            )

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.roles[0].name if user.roles else "USER"
        }

        return TokenResponse(
            access_token=create_access_token(data=token_data),
            refresh_token=create_refresh_token(data=token_data),
            role=str(token_data["role"]),
            user_id=UUID(str(user.id)),
            full_name=str(user.fullname),
            must_change_password=bool(user.must_change_password),
        )

    def create_staff(self, payload: StaffCreateRequest) -> RegisterResponse:
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        if payload.role_name == "APPLICANT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff accounts cannot have the applicant role."
            )

        staff_role = self._get_role_by_name(payload.role_name)

        user = User(
            fullname=payload.full_name,
            email=payload.email,
            username=payload.email,
            hashed_password=get_password_hash(payload.temporary_password),
            institution_name=None,
            is_active=True,
            must_change_password=True,
        )
        user.roles.append(staff_role)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return RegisterResponse(
            user_id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(user.fullname),
            role=payload.role_name,
            message=f"Staff account created for {user.fullname}. They must change their password on first login."
        )

    def change_password(self, user: User, payload: ChangePasswordRequest):
        if not verify_password(payload.current_password, str(user.hashed_password)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        user.hashed_password = get_password_hash(payload.new_password)
        user.must_change_password = False
        self.db.commit()
        return {"message": "Password updated successfully."}
