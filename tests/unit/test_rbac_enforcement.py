import pytest
from app.services.rbac_service import RBACService
from app.models.user import User, Role, Permission
from app.core.security.permissions import Permission as PermEnum

def test_role_boundary_applicant(db, applicant_user):
    """Verify that Applicant role cannot access administrative actions."""
    service = RBACService(db)
    
    # Setup Applicant Role with typical permissions
    applicant_role = Role(name="APPLICANT")
    p_submit = Permission(name=PermEnum.APPLICATIONS_SUBMIT, resource="applications", action="submit")
    p_read_own = Permission(name=PermEnum.APPLICATIONS_READ_OWN, resource="applications", action="read_own")
    applicant_role.permissions.extend([p_submit, p_read_own])
    
    applicant_user.roles = [applicant_role]
    db.commit()
    
    # Allowed
    assert service.has_permission_by_name(applicant_user, PermEnum.APPLICATIONS_SUBMIT) is True
    assert service.has_permission_by_name(applicant_user, PermEnum.APPLICATIONS_READ_OWN) is True
    
    # Denied
    assert service.has_permission_by_name(applicant_user, PermEnum.USERS_READ) is False
    assert service.has_permission_by_name(applicant_user, PermEnum.APPLICATIONS_READ_ALL) is False
    assert service.has_permission_by_name(applicant_user, PermEnum.WORKFLOW_MANAGE) is False

def test_role_boundary_reviewer(db, staff_user):
    """Verify that Reviewer role cannot approve (final decision) or manage users."""
    service = RBACService(db)
    
    # Setup Reviewer Role
    reviewer_role = Role(name="REVIEWER")
    p_read_all = Permission(name=PermEnum.APPLICATIONS_READ_ALL, resource="applications", action="read_all")
    p_transition = Permission(name=PermEnum.APPLICATIONS_TRANSITION, resource="applications", action="transition")
    reviewer_role.permissions.extend([p_read_all, p_transition])
    
    staff_user.roles = [reviewer_role]
    db.commit()
    
    # Allowed
    assert service.has_permission_by_name(staff_user, PermEnum.APPLICATIONS_READ_ALL) is True
    assert service.has_permission_by_name(staff_user, PermEnum.APPLICATIONS_TRANSITION) is True
    
    # Denied (Admin boundaries)
    assert service.has_permission_by_name(staff_user, PermEnum.USERS_CREATE) is False
    assert service.has_permission_by_name(staff_user, PermEnum.WORKFLOW_MANAGE) is False
    assert service.has_permission_by_name(staff_user, PermEnum.AUDIT_READ) is False

def test_role_boundary_admin(db):
    """Verify that Admin role has management permissions but respects RBAC logic."""
    service = RBACService(db)
    
    admin_user = User(
        email="admin@bnr.rw",
        username="admin",
        hashed_password="hashed_password",
        fullname="System Administrator"
    )
    admin_role = Role(name="ADMIN")
    p_users = Permission(name=PermEnum.USERS_CREATE, resource="users", action="create")
    p_workflow = Permission(name=PermEnum.WORKFLOW_MANAGE, resource="workflow", action="manage")
    admin_role.permissions.extend([p_users, p_workflow])
    
    admin_user.roles = [admin_role]
    db.add_all([admin_user, admin_role])
    db.commit()
    
    # Allowed
    assert service.has_permission_by_name(admin_user, PermEnum.USERS_CREATE) is True
    assert service.has_permission_by_name(admin_user, PermEnum.WORKFLOW_MANAGE) is True
    
    # Denied (unless specifically added or superuser)
    assert service.has_permission_by_name(admin_user, PermEnum.APPLICATIONS_SUBMIT) is False
