import math
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import (
    Application, ApplicationStatus, ApplicationStateHistory, User,
    ApprovalWorkflow
)
from app.services.application_fsm import ApplicationFSM
from app.services.document_service import DocumentService

class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application(self, applicant: User, data: dict) -> Application:
        # Handle declaration timestamp
        if data.get("declaration_accepted"):
            data["declaration_accepted_at"] = datetime.now(timezone.utc)

        # Automatically select active workflow if not provided
        if not data.get("workflow_id"):
            active_workflow = self.db.query(ApprovalWorkflow).filter(
                ApprovalWorkflow.is_active == True
            ).first()
            if not active_workflow:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No active workflow found in the system. Please contact administrator."
                )
            data["workflow_id"] = active_workflow.id
            
        application = Application(
            applicant_id=applicant.id,
            **data
        )
        self.db.add(application)
        self.db.flush()

        # Initialize document requirements
        doc_service = DocumentService(self.db)
        doc_service.initialize_application_requirements(application)

        # Record initial DRAFT state
        history = ApplicationStateHistory(
            application_id=application.id,
            from_status=ApplicationStatus.DRAFT,
            to_status=ApplicationStatus.DRAFT,
            changed_by_id=applicant.id,
            notes="Application created",
            level_number=0
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(application)
        return application

    def transition_state(
        self,
        application_id: str,
        current_user: User,
        action: str,
        notes: str | None = None,
        expected_version: int | None = None
    ) -> Application:
        query = self.db.query(Application).filter(Application.id == application_id)
        
        if expected_version is not None:
            query = query.filter(Application.version == expected_version)
            
        application = query.first()

        if not application:
            # Check if it exists at all to differentiate between 404 and 409
            exists = self.db.query(Application).filter(Application.id == application_id).first()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The application has been modified by another process. Please refresh and try again."
                )
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

        fsm = ApplicationFSM(application, self.db, current_user)

        # Execute transition
        if action == "submit":
            fsm.submit(notes)
        elif action == "approve":
            fsm.approve(notes)
        elif action == "reject":
            fsm.reject(notes)
        elif action == "request_information":
            fsm.request_information(notes)
        elif action == "resubmit":
            fsm.resubmit(notes)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown action: {action}")

        self.db.commit()
        self.db.refresh(application)
        return application

    def get_applications(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None
    ) -> dict:
        query = self.db.query(Application)

        # Applicants only see their own applications
        # Staff/Admin see all
        is_staff = any(role.name in ["ADMIN", "REVIEWER", "APPROVER"] for role in current_user.roles)
        if not is_staff:
            query = query.filter(Application.applicant_id == current_user.id)

        # Filters
        if status:
            query = query.filter(Application.status == status)
        if search:
            query = query.filter(Application.institution_name.ilike(f"%{search}%"))

        total_count = query.count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        offset = (page - 1) * page_size
        items = query.order_by(Application.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "items": items,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size
        }

    def get_application(self, application_id: str) -> Application:
        app = self.db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
        return app
