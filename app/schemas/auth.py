from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from uuid import UUID

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None
    is_active: Optional[bool] = None

class TokenResponse(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None  # seconds
    is_first_login: bool = False
    email: Optional[str] = None
    requires_role_selection: bool = False
    active_role: Optional[str] = None
    roles: list[str] = []
    detail: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ApplicantRegisterRequest(BaseModel):
    """
    Public registration — applicant only.
    """
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    institution_name: str = Field(..., min_length=2, max_length=512,
        description="Name of the institution applying for a license")

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class OTPResend(BaseModel):
    email: EmailStr

class StaffCreateRequest(BaseModel):
    """
    Admin-only staff provisioning.
    """
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    temporary_password: str = Field(..., min_length=8, max_length=128)
    role_name: str = Field(..., description="REVIEWER | APPROVER | ADMIN")

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class RegisterResponse(BaseModel):
    email: str
    detail: str

class UserBasicInfoUpdate(BaseModel):
    fullname: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None

class RefreshToken(BaseModel):
    refresh_token: str
