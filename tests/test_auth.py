import pytest
from app.services.rbac_service import RBACService
from app.models.user import User, Role, Permission

def test_applicant_permissions(db, applicant_user):
    """Test that an applicant has limited permissions."""
    service = RBACService(db)
    
    # By default, my fixture doesn't add roles to applicant. 
    # Let's add an APPLICANT role.
    role = Role(name="APPLICANT")
    perm = Permission(name="applications:submit", resource="applications", action="submit")
    role.permissions.append(perm)
    applicant_user.roles.append(role)
    db.commit()
    
    assert service.has_permission(applicant_user, "applications", "submit") is True
    assert service.has_permission(applicant_user, "users", "delete") is False

def test_staff_permissions(db, staff_user):
    """Test that a staff user has review permissions."""
    service = RBACService(db)
    
    # staff_user fixture already has STAFF role, let's add permission to it
    role = staff_user.roles[0]
    perm = Permission(name="applications:review", resource="applications", action="review")
    role.permissions.append(perm)
    db.commit()
    
    assert service.has_permission(staff_user, "applications", "review") is True
    assert service.has_permission(staff_user, "applications", "submit") is False

def test_superuser_permissions(db):
    """Test that a superuser has all permissions."""
    admin = User(
        email="admin@example.com",
        username="admin",
        hashed_password="hashed_password",
        fullname="Admin User",
        is_superuser=True
    )
    db.add(admin)
    db.commit()
    
    service = RBACService(db)
    assert service.has_permission(admin, "any", "action") is True
    assert service.has_permission(admin, "users", "delete") is True
