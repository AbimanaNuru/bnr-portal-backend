from enum import Enum
from app.core.security.permissions import Permission

class RoleName(str, Enum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    APPLICANT = "APPLICANT"

PERMISSION_CATEGORIES = [
    {"name": "User Management", "description": "Manage users, roles, and permissions"},
    {"name": "Workflow Management", "description": "Configure approval workflows and levels"},
    {"name": "Application Operations", "description": "Create, view, and transition bank applications"},
    {"name": "Document Operations", "description": "Upload, view, and manage application documents"},
]

PERMISSIONS = [
    # User Management
    {"name": Permission.USERS_READ, "description": "View users and their roles", "category": "User Management"},
    {"name": Permission.USERS_CREATE, "description": "Provision new staff accounts", "category": "User Management"},
    {"name": Permission.USERS_UPDATE, "description": "Manage user status and roles", "category": "User Management"},
    {"name": Permission.ROLES_MANAGE, "description": "Configure system roles", "category": "User Management"},
    
    # Workflow Management
    {"name": Permission.WORKFLOW_READ, "description": "View existing workflows and levels", "category": "Workflow Management"},
    {"name": Permission.WORKFLOW_MANAGE, "description": "Create or modify workflows and approval levels", "category": "Workflow Management"},
    
    # Application Operations
    {"name": Permission.APPLICATIONS_CREATE, "description": "Create a new bank application", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_READ, "description": "View a single application's details", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_READ_OWN, "description": "List own applications (applicants)", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_READ_ALL, "description": "List all applications in the system (staff)", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_UPDATE, "description": "Update application content", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_SUBMIT, "description": "Submit a draft application for review", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_RESUBMIT, "description": "Resubmit after information is requested", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_START_REVIEW, "description": "Initiate the review process", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_COMPLETE_REVIEW, "description": "Finish the review process", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_REQUEST_INFO, "description": "Request more details from the applicant", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_APPROVE, "description": "Grant approval at the current level", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_REJECT, "description": "Deny the application", "category": "Application Operations"},
    {"name": Permission.APPLICATIONS_TRANSITION, "description": "General workflow transition permission", "category": "Application Operations"},
    
    # Document Operations
    {"name": Permission.DOCUMENTS_UPLOAD, "description": "Upload required documents", "category": "Document Operations"},
    {"name": Permission.DOCUMENTS_READ, "description": "Download or view documents", "category": "Document Operations"},
    {"name": Permission.DOCUMENTS_MANAGE_TYPES, "description": "Define required document types", "category": "Document Operations"},
    
    # Audit Logs
    {"name": Permission.AUDIT_READ, "description": "View system audit logs", "category": "User Management"},
]

ROLE_PERMISSIONS = {
    RoleName.ADMIN: [
        Permission.USERS_READ, Permission.USERS_CREATE, Permission.USERS_UPDATE, Permission.ROLES_MANAGE,
        Permission.WORKFLOW_READ, Permission.WORKFLOW_MANAGE,
        Permission.APPLICATIONS_READ, Permission.APPLICATIONS_READ_ALL, 
        Permission.APPLICATIONS_START_REVIEW, Permission.APPLICATIONS_COMPLETE_REVIEW,
        Permission.APPLICATIONS_REQUEST_INFO, Permission.APPLICATIONS_APPROVE, Permission.APPLICATIONS_REJECT,
        Permission.APPLICATIONS_TRANSITION,
        Permission.DOCUMENTS_READ, Permission.DOCUMENTS_MANAGE_TYPES,
        Permission.AUDIT_READ,
    ],
    RoleName.REVIEWER: [
        Permission.APPLICATIONS_READ, Permission.APPLICATIONS_READ_ALL, 
        Permission.APPLICATIONS_START_REVIEW, Permission.APPLICATIONS_COMPLETE_REVIEW, Permission.APPLICATIONS_REQUEST_INFO,
        Permission.APPLICATIONS_TRANSITION,
        Permission.DOCUMENTS_READ,
        Permission.WORKFLOW_READ,
    ],
    RoleName.APPROVER: [
        Permission.APPLICATIONS_READ, Permission.APPLICATIONS_READ_ALL, 
        Permission.APPLICATIONS_APPROVE, Permission.APPLICATIONS_REJECT,
        Permission.APPLICATIONS_TRANSITION,
        Permission.DOCUMENTS_READ,
        Permission.WORKFLOW_READ,
    ],
    RoleName.APPLICANT: [
        Permission.APPLICATIONS_CREATE, Permission.APPLICATIONS_READ, Permission.APPLICATIONS_READ_OWN,
        Permission.APPLICATIONS_UPDATE, Permission.APPLICATIONS_SUBMIT, Permission.APPLICATIONS_RESUBMIT,
        Permission.DOCUMENTS_UPLOAD, Permission.DOCUMENTS_READ,
    ],
}

DOCUMENT_TYPES = [
    {"name": "Certificate of Incorporation", "description": "Official document showing the registration of the bank", "is_required": True, "display_order": 1},
    {"name": "Board Resolution", "description": "Resolution from the board of directors authorizing the application", "is_required": True, "display_order": 2},
    {"name": "Business Plan", "description": "Detailed 3-5 year business strategy and financial projections", "is_required": True, "display_order": 3},
    {"name": "Proof of Minimum Capital", "description": "Bank statements or audit certificates showing required capital", "is_required": True, "display_order": 4},
    {"name": "Internal Control Manuals", "description": "Policies for risk management, compliance, and internal audit", "is_required": True, "display_order": 5},
    {"name": "Fit and Proper Questionnaires", "description": "Background checks for shareholders and key officers", "is_required": True, "display_order": 6},
    {"name": "Tax Clearance Certificate", "description": "Valid tax clearance from RRA", "is_required": False, "display_order": 7},
]

DEFAULT_WORKFLOWS = [
    {
        "name": "Commercial Bank Licensing Workflow",
        "description": "Standard multi-level approval process for new commercial bank applications",
        "levels": [
            {
                "level_number": 1,
                "name": "Initial Technical Review",
                "required_approvals": 1,
                "roles": [RoleName.REVIEWER]
            },
            {
                "level_number": 2,
                "name": "Directorate Approval",
                "required_approvals": 1,
                "roles": [RoleName.APPROVER]
            },
            {
                "level_number": 3,
                "name": "Board Final Decision",
                "required_approvals": 1,
                "roles": [RoleName.ADMIN]
            }
        ]
    }
]
