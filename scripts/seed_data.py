import sys
import os
from uuid import uuid4
from typing import cast, List

# Add the parent directory to the path so we can import 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.user import User, Role, Permission, PermissionCategory
from app.core.security.security import get_password_hash
from app.models.documents import DocumentTypeDefinition
from app.models.approval_workflow import ApprovalWorkflow, ApprovalLevel
from app.core.predefined_data import PERMISSION_CATEGORIES, PERMISSIONS, ROLE_PERMISSIONS, RoleName, DOCUMENT_TYPES, DEFAULT_WORKFLOWS

def seed_data():
    db = SessionLocal()
    try:
        print("🌱 Starting Data Seeding...")

        # 1. Seed Permission Categories
        category_map = {}
        for cat_data in PERMISSION_CATEGORIES:
            cat = db.query(PermissionCategory).filter(PermissionCategory.name == cat_data["name"]).first()
            if not cat:
                cat = PermissionCategory(
                    id=str(uuid4()),
                    name=cat_data["name"],
                    description=cat_data["description"]
                )
                db.add(cat)
                db.flush()
                print(f"  ✅ Created Category: {cat.name}")
            category_map[cat_data["name"]] = cat

        # 2. Seed Permissions
        permission_map = {}
        for perm_data in PERMISSIONS:
            perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()

            # Split name to get resource and action
            # e.g. "users:read" -> resource="users", action="read"
            resource, action = perm_data["name"].split(":")

            if not perm:
                perm = Permission(
                    id=str(uuid4()),
                    name=perm_data["name"],
                    resource=resource,
                    action=action,
                    description=perm_data["description"],
                    category_id=category_map[perm_data["category"]].id
                )
                db.add(perm)
                db.flush()
                print(f"  ✅ Created Permission: {perm.name}")
            permission_map[perm_data["name"]] = perm

        # 3. Seed Roles and Assign Permissions
        for role_name, perms_list in ROLE_PERMISSIONS.items():
            name_str = role_name.value if hasattr(role_name, "value") else str(role_name)
            role = db.query(Role).filter(Role.name == name_str).first()
            if not role:
                role = Role(
                    id=str(uuid4()),
                    name=name_str,
                    description=f"Standard {name_str} role for the portal"
                )
                db.add(role)
                db.flush()
                print(f"  ✅ Created Role: {role.name}")

            # Update permissions
            current_perm_names = [p.name for p in role.permissions]
            for p_name in perms_list:
                if p_name not in current_perm_names:
                    role.permissions.append(permission_map[p_name])

            print(f"  🛡️ Assigned {len(perms_list)} permissions to {role_name.value}")

        # 4. Seed Specific Development Accounts
        dev_accounts = [
            {
                "email": "applicant@bnr-dev.rw",
                "password": "applicant123",
                "fullname": "BNR Dev Applicant",
                "role": RoleName.APPLICANT,
                "is_superuser": False
            },
            {
                "email": "reviewer@bnr-dev.rw",
                "password": "reviewer123",
                "fullname": "BNR Dev Reviewer",
                "role": RoleName.REVIEWER,
                "is_superuser": False
            },
            {
                "email": "approver@bnr-dev.rw",
                "password": "approver123",
                "fullname": "BNR Dev Approver",
                "role": RoleName.APPROVER,
                "is_superuser": False
            },
            {
                "email": "admin@bnr-dev.rw",
                "password": "admin123",
                "fullname": "BNR Dev Administrator",
                "role": RoleName.ADMIN,
                "is_superuser": True
            }
        ]

        for acc in dev_accounts:
            user = db.query(User).filter(User.email == acc["email"]).first()
            if not user:
                user = User(
                    id=str(uuid4()),
                    email=acc["email"],
                    username=acc["email"], # Use email to avoid unique constraint issues
                    fullname=acc["fullname"],
                    hashed_password=get_password_hash(acc["password"]),
                    is_active=True,
                    is_superuser=acc["is_superuser"],
                    email_verified=True,
                    must_change_password=False
                )

                # Assign role
                role_name_val = acc["role"].value if hasattr(acc["role"], "value") else str(acc["role"])
                role = db.query(Role).filter(Role.name == role_name_val).first()
                if role:
                    user.roles.append(role)

                db.add(user)
                print(f"  👤 Created Dev Account: {acc['email']} (Role: {role_name_val})")

        db.flush() # Ensure users are queryable before the next step

        # Get an admin user for subsequent steps
        admin_role_name = RoleName.ADMIN.value if hasattr(RoleName.ADMIN, "value") else str(RoleName.ADMIN)
        admin_user = db.query(User).join(User.roles).filter(Role.name == admin_role_name).first()

        if not admin_user:
            # Fallback if somehow not created above
            admin_user = db.query(User).filter(User.is_superuser == True).first()

        if not admin_user:
             # Critical failure if no admin exists
             raise ValueError("No admin user found to associate with document types. Seeding aborted.")

        # 5. Seed Document Type Definitions
        for doc_data in DOCUMENT_TYPES:
            doc_type = db.query(DocumentTypeDefinition).filter(DocumentTypeDefinition.name == doc_data["name"]).first()
            if not doc_type:
                doc_type = DocumentTypeDefinition(
                    name=doc_data["name"],
                    description=doc_data["description"],
                    is_required=doc_data["is_required"],
                    display_order=doc_data["display_order"],
                    created_by_id=admin_user.id
                )
                db.add(doc_type)
                print(f"  📄 Created Document Type: {doc_type.name}")

        # 6. Seed Approval Workflows and Levels
        # Deactivate all existing workflows first to ensure only the ones
        # in the current config are considered "Active"
        db.query(ApprovalWorkflow).update({ApprovalWorkflow.is_active: False})
        db.flush()

        for wf_data in DEFAULT_WORKFLOWS:
            workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.name == wf_data["name"]).first()
            if not workflow:
                workflow = ApprovalWorkflow(
                    id=str(uuid4()),
                    name=wf_data["name"],
                    description=wf_data["description"],
                    is_active=True
                )
                db.add(workflow)
                db.flush()
                print(f"  ⛓️ Created Workflow: {workflow.name}")
            else:
                workflow.is_active = True
                workflow.description = wf_data["description"]
                print(f"  ⛓️ Updated Workflow (Active): {workflow.name}")

            for lvl_data in wf_data["levels"]:
                level = db.query(ApprovalLevel).filter(
                    ApprovalLevel.workflow_id == workflow.id,
                    ApprovalLevel.level_number == lvl_data["level_number"]
                ).first()

                if not level:
                    level = ApprovalLevel(
                        id=str(uuid4()),
                        workflow_id=workflow.id,
                        level_number=cast(int, lvl_data["level_number"]),
                        name=cast(str, lvl_data["name"]),
                        required_approvals=cast(int, lvl_data["required_approvals"])
                    )
                    db.add(level)
                    print(f"    🚦 Created Level {level.level_number}: {level.name}")
                else:
                    level.name = cast(str, lvl_data["name"])
                    level.required_approvals = cast(int, lvl_data["required_approvals"])
                    print(f"    🚦 Updated Level {level.level_number}: {level.name}")

                # Sync roles for the level
                level.roles = []
                roles_list = cast(List, lvl_data["roles"])
                for role_item in roles_list:
                    role_name_str = role_item.value if hasattr(role_item, "value") else str(role_item)
                    role = db.query(Role).filter(Role.name == role_name_str).first()
                    if role:
                        level.roles.append(role)

        db.commit()
        print("✨ Data Seeding Complete!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
