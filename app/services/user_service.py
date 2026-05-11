import os
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.models.user import User, Role, Permission, PermissionCategory
from app.schemas.user_management import UserStatusUpdate
from datetime import datetime
import secrets
import string
from app.core.security.security import get_password_hash
from app.services.mail import send_email, EmailType

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_users_paginated(
        self, 
        page: int = 1, 
        page_size: int = 20, 
        search: Optional[str] = None,
        user_role: Optional[str] = None,
        user_status: Optional[bool] = None
    ) -> Tuple[List[User], int]:
        query = self.db.query(User).filter(User.deleted_at == None)

        if search:
            search_filter = or_(
                User.fullname.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone_number.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)

        if user_role:
            query = query.join(User.roles).filter(Role.name == user_role)

        if user_status is not None:
            query = query.filter(User.is_active == user_status)

        total = query.count()
        users = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return users, total

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id, User.deleted_at == None).first()

    def soft_delete_user(self, user_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if user:
            user.deleted_at = datetime.now()
            self.db.commit()
            return True
        return False

    def update_user_status(self, user_id: str, status_update: UserStatusUpdate) -> bool:
        user = self.get_user_by_id(user_id)
        if user:
            user.is_active = status_update.is_active
            self.db.commit()
            return True
        return False

    # ─── Role Management ──────────────────────────────────────────────────────

    def list_roles(self) -> List[Role]:
        return self.db.query(Role).all()

    def get_user_roles(self, user_id: str) -> List[Role]:
        user = self.get_user_by_id(user_id)
        return list(user.roles) if user else []  # type: ignore

    def assign_role_to_user(self, user_id: str, role_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if user and role:
            if role not in user.roles:
                user.roles.append(role)
                self.db.commit()
            return True
        return False

    def remove_role_from_user(self, user_id: str, role_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if user and role:
            if role in user.roles:
                user.roles.remove(role)
                self.db.commit()
            return True
        return False

    # ─── Permission Management ────────────────────────────────────────────────

    def list_permissions(self) -> List[Permission]:
        return self.db.query(Permission).all()

    def list_permission_categories(self) -> List[PermissionCategory]:
        return self.db.query(PermissionCategory).all()

    def assign_permission_to_role(self, role_id: str, permission_id: str) -> bool:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        permission = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if role and permission:
            if permission not in role.permissions:
                role.permissions.append(permission)
                self.db.commit()
            return True
        return False

    def remove_permission_from_role(self, role_id: str, permission_id: str) -> bool:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        permission = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if role and permission:
            if permission in role.permissions:
                role.permissions.remove(permission)
                self.db.commit()
            return True
        return False

    def invite_user(self, email: str, fullname: str, role_id: str) -> User:
        # Check if user already exists
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            if existing.deleted_at:
                # Reactivate if previously deleted
                existing.deleted_at = None
                existing.is_active = True
                existing.fullname = fullname
            else:
                raise ValueError(f"User with email {email} already exists")
            user = existing
        else:
            # Generate random password
            temp_password = self._generate_random_password()
            
            user = User(
                email=email,
                fullname=fullname,
                username=email, # Use email as username
                hashed_password=get_password_hash(temp_password),
                is_active=True,
                email_verified=True,
                must_change_password=True
            )
            self.db.add(user)
            self.db.flush()

        # Assign role
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ValueError(f"Role with ID {role_id} not found")
        
        if role not in user.roles:
            user.roles.append(role)
        
        self.db.commit()
        self.db.refresh(user)

        # Send invitation email
        send_email(
            email_type=EmailType.STAFF_ACCOUNT_CREATED,
            recipient_email=email,
            user_fullname=fullname,
            temporary_password=temp_password if not existing else "[Check previous email]",
            login_link=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/auth/login", # Configurable
            role=str(role.name)
        )
        
        return user

    def re_invite_user(self, user_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        # Generate new temporary password
        temp_password = self._generate_random_password()
        user.hashed_password = get_password_hash(temp_password)
        user.must_change_password = True
        
        role_name = user.roles[0].name if user.roles else "Staff"
        
        self.db.commit()

        # Resend email
        send_email(
            email_type=EmailType.STAFF_ACCOUNT_CREATED,
            recipient_email=str(user.email),
            user_fullname=str(user.fullname),
            temporary_password=temp_password,
            login_link=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/auth/login",
            role=str(role_name)
        )
        return True

    def _generate_random_password(self, length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
