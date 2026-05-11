from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import List
from uuid import UUID

from app.models.approval_workflow import ApprovalWorkflow, ApprovalLevel
from app.models.user import Role
from app.schemas.approval_workflow import (
    ApprovalWorkflowCreate,
    ApprovalWorkflowUpdate,
    ApprovalLevelCreate,
    ApprovalLevelUpdate
)

class WorkflowService:
    def __init__(self, db: Session):
        self.db = db

    # --- Workflow Management ---

    def create_workflow(self, data: ApprovalWorkflowCreate) -> ApprovalWorkflow:
        try:
            workflow = ApprovalWorkflow(
                name=data.name,
                description=data.description,
                is_active=data.is_active
            )
            self.db.add(workflow)
            self.db.flush()

            for level_data in data.levels:
                self._add_level(str(workflow.id), level_data)

            self.db.commit()
            self.db.refresh(workflow)
            return workflow
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow with this name already exists or invalid data provided."
            )

    def get_workflow(self, workflow_id: str) -> ApprovalWorkflow:
        workflow = self.db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return workflow

    def list_workflows(self) -> List[ApprovalWorkflow]:
        return self.db.query(ApprovalWorkflow).all()

    def update_workflow(self, workflow_id: str, data: ApprovalWorkflowUpdate) -> ApprovalWorkflow:
        workflow = self.get_workflow(workflow_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("is_active") is True:
            # Deactivate all others
            self.db.query(ApprovalWorkflow).filter(
                ApprovalWorkflow.id != workflow_id
            ).update({"is_active": False}, synchronize_session=False)
            
            from app.models.application import Application
            self.db.query(Application).update({"workflow_id": workflow_id}, synchronize_session=False)
        
        elif update_data.get("is_active") is False:
            # Prevent deactivating the ONLY active workflow
            active_count = self.db.query(ApprovalWorkflow).filter(ApprovalWorkflow.is_active == True).count()
            if active_count <= 1 and workflow.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the only active workflow. Activate another one first."
                )

        for key, value in update_data.items():
            setattr(workflow, key, value)

        try:
            self.db.commit()
            self.db.refresh(workflow)
            return workflow
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow name might already be taken.",
            )

    def delete_workflow(self, workflow_id: str):
        workflow = self.get_workflow(workflow_id)
        self.db.delete(workflow)
        self.db.commit()

    # --- Level Management ---

    def _add_level(self, workflow_id: str, data: ApprovalLevelCreate) -> ApprovalLevel:
        level = ApprovalLevel(
            workflow_id=workflow_id,
            level_number=data.level_number,
            name=data.name,
            required_approvals=data.required_approvals
        )
        self.db.add(level)
        self.db.flush()
        
        if data.role_ids:
            roles = self.db.query(Role).filter(Role.id.in_([str(r_id) for r_id in data.role_ids])).all()
            if len(roles) != len(data.role_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more role IDs are invalid"
                )
            level.roles = roles
        return level

    def add_level_to_workflow(self, workflow_id: str, data: ApprovalLevelCreate) -> ApprovalLevel:
        workflow = self.get_workflow(workflow_id) # ensure it exists
        try:
            level = self._add_level(workflow_id, data)
            self.db.commit()
            self.db.refresh(level)
            return level
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A level with this number might already exist for this workflow."
            )

    def get_level(self, level_id: str) -> ApprovalLevel:
        level = self.db.query(ApprovalLevel).filter(ApprovalLevel.id == level_id).first()
        if not level:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval level not found")
        return level

    def update_level(self, level_id: str, data: ApprovalLevelUpdate) -> ApprovalLevel:
        level = self.get_level(level_id)
        
        if data.role_ids is not None:
            roles = self.db.query(Role).filter(Role.id.in_([str(r_id) for r_id in data.role_ids])).all()
            if len(roles) != len(data.role_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more role IDs are invalid"
                )
            level.roles = roles

        update_data = data.model_dump(exclude_unset=True, exclude={"role_ids"})
        for key, value in update_data.items():
            setattr(level, key, value)
            
        try:
            self.db.commit()
            self.db.refresh(level)
            return level
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data or level number conflict."
            )

    def remove_level(self, level_id: str):
        level = self.get_level(level_id)
        self.db.delete(level)
        self.db.commit()

    # --- Role Assignment to Level ---

    def assign_role_to_level(self, level_id: str, role_id: str) -> ApprovalLevel:
        level = self.get_level(level_id)
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        
        if role not in level.roles:
            level.roles.append(role)
            self.db.commit()
            self.db.refresh(level)
        return level

    def remove_role_from_level(self, level_id: str, role_id: str) -> ApprovalLevel:
        level = self.get_level(level_id)
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
            
        if role in level.roles:
            level.roles.remove(role)
            self.db.commit()
            self.db.refresh(level)
        return level
