from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import get_db
from app.models.user import User
from app.services.rbac_service import RBACService
from app.core.security.security import SECRET_KEY, ALGORITHM
from app.schemas.auth import TokenData

security_scheme = HTTPBearer()

async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = auth.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user

def require_permission(permission_name: str):
    """
    Dependency to check for a specific permission by name.
    Usage: Depends(require_permission(Permission.USERS_READ))
    """
    def permission_dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        rbac = RBACService(db)
        if not rbac.has_permission_by_name(current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name}"
            )
        return current_user
    return permission_dependency

def require_any_permission(permission_names: list[str]):
    """
    Dependency to check if the user has AT LEAST ONE of the specified permissions.
    Usage: Depends(require_any_permission([Permission.A, Permission.B]))
    """
    def permission_dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        rbac = RBACService(db)
        for name in permission_names:
            if rbac.has_permission_by_name(current_user, name):
                return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: Requires one of {', '.join(permission_names)}"
        )
    return permission_dependency
