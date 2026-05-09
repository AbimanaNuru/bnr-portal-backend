from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, RefreshToken, UserRegister, LoginRequest
from app.core.security.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)




@router.post("/login", response_model=Token)
async def login_for_frontend(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Standard JSON endpoint for the frontend.
    Accepts a JSON body with `email` and `password`.
    """
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support."
        )

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username
    }

    return {
        "access_token": create_access_token(data=token_data),
        "refresh_token": create_refresh_token(data=token_data),
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    token_data: RefreshToken,
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise credentials_exception

        new_token_data = {
            "sub": str(user.id),
            "email": user.email,
            "username": user.username
        }

        return {
            "access_token": create_access_token(data=new_token_data),
            "refresh_token": token_data.refresh_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise credentials_exception


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email or username already exists"
        )

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        fullname=user_data.fullname,
        phone_number=user_data.phone_number,
        hashed_password=get_password_hash(user_data.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token_payload = {
        "sub": str(new_user.id),
        "email": new_user.email,
        "username": new_user.username
    }

    return {
        "access_token": create_access_token(data=token_payload),
        "refresh_token": create_refresh_token(data=token_payload),
        "token_type": "bearer"
    }
