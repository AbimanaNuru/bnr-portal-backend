from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
# from app.core.auth import get_current_active_user # Assuming this will be implemented
from app.services.rbac_service import RBACService

# Dummy for now to avoid import error
async def get_current_active_user(db: Session = Depends(get_db)) -> User:
    # This should be replaced with actual auth logic
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_permission(resource: str, action: str):
    """
    Senior-level permission dependency
    Example: require_permission("application", "approve")
    """
    def permission_dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        rbac = RBACService(db)
        if not rbac.has_permission(current_user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}"
            )
        return current_user
    return permission_dependency
