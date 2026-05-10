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
            role = db.query(Role).filter(Role.name == role_name.value).first()
            if not role:
                role = Role(
                    id=str(uuid4()),
                    name=role_name.value,
                    description=f"Standard {role_name.value} role for the portal"
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

        # 4. Seed Default Admin User
        admin_email = "admin@bnr.rw"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            admin_user = User(
                id=str(uuid4()),
                email=admin_email,
                username="admin",
                fullname="BNR System Administrator",
                hashed_password=get_password_hash("Admin@123"),
                is_active=True,
                is_superuser=True,
                email_verified=True,
                must_change_password=False
            )

            # Assign ADMIN role
            admin_role = db.query(Role).filter(Role.name == RoleName.ADMIN.value).first()
            if admin_role:
                admin_user.roles.append(admin_role)

            db.add(admin_user)
            print(f"  👤 Created Default Admin: {admin_email} (Password: Admin@123)")

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
        for wf_data in DEFAULT_WORKFLOWS:
            workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.name == wf_data["name"]).first()
            if not workflow:
                workflow = ApprovalWorkflow(
                    id=str(uuid4()),
                    name=wf_data["name"],
                    description=wf_data["description"]
                )
                db.add(workflow)
                db.flush()
                print(f"  ⛓️ Created Workflow: {workflow.name}")
                
                for lvl_data in wf_data["levels"]:
                    level = ApprovalLevel(
                        id=str(uuid4()),
                        workflow_id=workflow.id,
                        level_number=lvl_data["level_number"],
                        name=lvl_data["name"],
                        required_approvals=lvl_data["required_approvals"]
                    )
                    
                    # Add roles to level
                    roles_list = cast(List, lvl_data["roles"])
                    for role_enum in roles_list:
                        role = db.query(Role).filter(Role.name == role_enum.value).first()
                        if role:
                            level.roles.append(role)
                    
                    db.add(level)
                    print(f"    🚦 Created Level {level.level_number}: {level.name}")

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
