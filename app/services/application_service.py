from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Application, ApplicationStatus, ApplicationStateHistory,
    User, ApprovalWorkflow,
)
from app.services.application_fsm import ApplicationFSM
from app.services.document_service import DocumentService


class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application(self, applicant: User, data: dict) -> Application:
        if data.get("declaration_accepted"):
            data["declaration_accepted_at"] = datetime.now(timezone.utc)

        # Always use the currently active workflow
        active_wf = (
            self.db.query(ApprovalWorkflow)
            .filter(ApprovalWorkflow.is_active == True)
            .first()
        )
        if not active_wf:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active workflow configured. Contact an administrator.",
            )
        data["workflow_id"] = active_wf.id

        application = Application(applicant_id=applicant.id, **data)
        self.db.add(application)
        self.db.flush()

        DocumentService(self.db).initialize_application_requirements(application)

        self.db.add(
            ApplicationStateHistory(
                application_id=application.id,
                from_status=ApplicationStatus.DRAFT,
                to_status=ApplicationStatus.DRAFT,
                changed_by_id=applicant.id,
                notes="Application created",
                level_number=0,
            )
        )
        self.db.commit()
        self.db.refresh(application)
        return application

    def transition_state(
        self,
        application_id: str,
        current_user: User,
        action: str,
        notes: str | None = None,
        expected_version: int | None = None,
    ) -> Application:
        query = self.db.query(Application).filter(Application.id == application_id)

        if expected_version is not None:
            query = query.filter(Application.version == expected_version)

        application = query.first()

        if not application:
            exists = self.db.query(Application).filter(Application.id == application_id).first()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The application has been modified by another process. Please refresh and try again.",
                )
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

        fsm = ApplicationFSM(application, self.db, current_user)

        dispatch = {
            "submit": fsm.submit,
            "approve": fsm.approve,
            "reject": fsm.reject,
            "request_information": fsm.request_information,
            "request_info": fsm.request_information,
            "resubmit": fsm.resubmit,
            "start_review": fsm.start_review,
            "complete_review": fsm.complete_review,
        }
        action_lower = action.lower()
        handler = dispatch.get(action_lower)
        if not handler:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown action: {action}")

        handler(notes)
        self.db.commit()
        self.db.refresh(application)
        return application

    def get_applications(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
        own_only: bool = False,
    ) -> dict:
        query = self.db.query(Application)

        if own_only:
            query = query.filter(Application.applicant_id == current_user.id)

        if status:
            query = query.filter(Application.status == status)
        if search:
            query = query.filter(Application.institution_name.ilike(f"%{search}%"))

        total_count = query.count()
        offset = (page - 1) * page_size
        items = query.order_by(Application.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "items": items,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size if total_count else 1,
            "current_page": page,
            "page_size": page_size,
        }

    def get_application(self, application_id: str) -> Application:
        app = self.db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

        if not app.workflow or not app.workflow.is_active:
            active_wf = (
                self.db.query(ApprovalWorkflow)
                .filter(ApprovalWorkflow.is_active == True)
                .first()
            )
            if active_wf and app.workflow_id != active_wf.id:
                app.workflow_id = active_wf.id
                self.db.commit()
                self.db.refresh(app)

        return app
