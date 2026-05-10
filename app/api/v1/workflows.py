from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.security.dependencies import require_permission, get_current_active_user
from app.core.security.permissions import Permission
from app.models import User
from app.schemas.approval_workflow import (
    ApprovalWorkflowCreate,
    ApprovalWorkflowRead,
    ApprovalWorkflowUpdate,
    ApprovalLevelCreate,
    ApprovalLevelRead,
    ApprovalLevelUpdate,
    RoleAssignRequest
)
from app.services.workflow_service import WorkflowService
from app.services.audit_service import audit

router = APIRouter(prefix="/workflows", tags=["Workflows"])

# --- Workflow Management Endpoints ---

@router.post("/", status_code=status.HTTP_201_CREATED)
@audit(action="WORKFLOW_CREATE", resource="workflow")
def create_workflow(
    data: ApprovalWorkflowCreate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    workflow = service.create_workflow(data)
    
    # Audit
    request.state.audit_resource_id = str(workflow.id)
    request.state.audit_new = {"name": workflow.name}
    
    return {"detail": "Workflow created successfully", "id": str(workflow.id)}

@router.get("/", response_model=List[ApprovalWorkflowRead])
def list_workflows(
    current_user: User = Depends(require_permission(Permission.WORKFLOW_READ)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    return service.list_workflows()

@router.get("/{workflow_id}", response_model=ApprovalWorkflowRead)
def get_workflow(
    workflow_id: str,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_READ)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    return service.get_workflow(workflow_id)

@router.put("/{workflow_id}")
@audit(action="WORKFLOW_UPDATE", resource="workflow")
def update_workflow(
    workflow_id: str,
    data: ApprovalWorkflowUpdate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    workflow = service.update_workflow(workflow_id, data)
    
    # Audit
    request.state.audit_resource_id = str(workflow_id)
    request.state.audit_new = {"name": workflow.name}
    
    return {"detail": "Workflow updated successfully", "id": str(workflow.id)}

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    service.delete_workflow(workflow_id)

# --- Level Management Endpoints ---

@router.post("/{workflow_id}/levels", status_code=status.HTTP_201_CREATED)
@audit(action="WORKFLOW_LEVEL_ADD", resource="workflow_level")
def add_level_to_workflow(
    workflow_id: str,
    data: ApprovalLevelCreate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    level = service.add_level_to_workflow(workflow_id, data)
    
    # Audit
    request.state.audit_resource_id = str(level.id)
    request.state.audit_new = {"name": level.name, "workflow_id": workflow_id}
    
    return {"detail": "Level added successfully", "id": str(level.id)}

@router.get("/{workflow_id}/levels", response_model=List[ApprovalLevelRead])
def get_workflow_levels(
    workflow_id: str,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_READ)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    workflow = service.get_workflow(workflow_id)
    return workflow.levels

@router.put("/levels/{level_id}")
def update_level(
    level_id: str,
    data: ApprovalLevelUpdate,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    level = service.update_level(level_id, data)
    return {"detail": "Level updated successfully", "id": str(level.id)}

@router.delete("/levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_level(
    level_id: str,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    service.remove_level(level_id)

# --- Role Assignment Endpoints ---

@router.post("/levels/{level_id}/roles")
@audit(action="WORKFLOW_LEVEL_ROLE_ASSIGN", resource="workflow_level")
def assign_role_to_level(
    level_id: str,
    request_data: RoleAssignRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    level = service.assign_role_to_level(level_id, str(request_data.role_id))
    
    # Audit
    request.state.audit_resource_id = str(level_id)
    request.state.audit_new = {"role_id": str(request_data.role_id)}
    
    return {"detail": "Role assigned successfully", "id": str(level.id)}

@router.delete("/levels/{level_id}/roles/{role_id}", response_model=ApprovalLevelRead)
def remove_role_from_level(
    level_id: str,
    role_id: str,
    current_user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db)
):
    service = WorkflowService(db)
    return service.remove_role_from_level(level_id, role_id)
