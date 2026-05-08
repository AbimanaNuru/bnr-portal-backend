from sqlalchemy.orm import Session
from app.models import User


class RBACService:
    def __init__(self, db: Session):
        self.db = db

    def has_permission(self, user: User, resource: str, action: str) -> bool:
        if user.is_superuser:
            return True

        for role in user.roles:
            for permission in role.permissions:
                if (permission.resource == resource and 
                    permission.action == action):
                    return True
        return False

    def has_role(self, user: User, role_name: str) -> bool:
        return any(role.name == role_name for role in user.roles)
