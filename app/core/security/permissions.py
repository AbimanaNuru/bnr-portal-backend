from enum import StrEnum

class Permission(StrEnum):
    # Users
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"

    # Roles & Permissions
    ROLES_MANAGE = "roles:manage"
    PERMISSIONS_MANAGE = "permissions:manage"

    # Workflow
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_MANAGE = "workflow:manage"

    # Applications
    APPLICATIONS_READ = "applications:read"
    APPLICATIONS_CREATE = "applications:create"
    APPLICATIONS_UPDATE = "applications:update"
    APPLICATIONS_TRANSITION = "applications:transition"

    # Documents
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_MANAGE_TYPES = "documents:manage_types"

    # Audit Logs
    AUDIT_READ = "audit:read"
