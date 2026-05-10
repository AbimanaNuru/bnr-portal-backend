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
from app.services.mail import send_email, EmailType
import secrets
from datetime import datetime, timezone, timedelta

OTP_EXPIRE_MINUTES = 15

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

        otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

        user = User(
            fullname=payload.full_name,
            email=payload.email,
            username=payload.email,  # Using email as username for simplicity
            hashed_password=get_password_hash(secrets.token_urlsafe(32)), # No password provided yet
            institution_name=payload.institution_name,
            is_active=True,
            must_change_password=True,
            otp=otp_code,
            otp_expiry=otp_expiry
        )
        user.roles.append(applicant_role)

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        send_email(
            email_type=EmailType.OTP_VERIFICATION,
            recipient_email=str(user.email),
            user_fullname=str(user.fullname),
            otp=otp_code,
        )

        return RegisterResponse(
            user_id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(user.fullname),
            role="APPLICANT",
            message="Account created successfully. An OTP has been sent to your email to complete registration."
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

        return self._generate_token_response(user)

    def _generate_token_response(self, user: User) -> TokenResponse:
        active_role = user.roles[0].name if user.roles else "USER"
        roles = [r.name for r in user.roles]
        
        token_data = {
            "sub": str(user.id),
            "email": str(user.email),
            "role": active_role
        }

        return TokenResponse(
            access_token=create_access_token(data=token_data),
            refresh_token=create_refresh_token(data=token_data),
            token_type="bearer",
            expires_in=86400, # 24 hours assumed
            is_first_login=bool(user.must_change_password),
            email=str(user.email),
            requires_role_selection=len(roles) > 1,
            active_role=active_role,
            roles=roles,
            detail="Authentication successful"
        )

    def verify_otp(self, email: str, otp: str) -> dict:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.otp is None or user.otp != otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")

        expiry_time = (
            user.otp_expiry.replace(tzinfo=timezone.utc)
            if user.otp_expiry and user.otp_expiry.tzinfo is None
            else user.otp_expiry
        )
        if not expiry_time or datetime.now(timezone.utc) > expiry_time:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP has expired")

        user.otp = None
        user.otp_expiry = None
        user.last_login_at = datetime.now(timezone.utc)
        
        self.db.commit()

        return self._generate_token_response(user).model_dump()

    def resend_otp(self, email: str) -> dict:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
        
        user.otp = otp_code
        user.otp_expiry = otp_expiry
        self.db.commit()

        send_email(
            email_type=EmailType.OTP_VERIFICATION,
            recipient_email=str(user.email),
            user_fullname=str(user.fullname),
            otp=otp_code,
        )

        return {"detail": "OTP resent successfully"}

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
