from pydantic import BaseModel, EmailStr
from typing import Optional

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    user_id: str | None = None
    is_active: bool | None = None

class RefreshToken(BaseModel):
    refresh_token: str

class UserRegister(BaseModel):
    email: EmailStr
    username: str
    fullname: str
    password: str
    phone_number: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
