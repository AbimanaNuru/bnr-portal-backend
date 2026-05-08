from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import (
    Application, ApplicationStatus, ApplicationStateHistory, User
)
from app.services.application_fsm import ApplicationFSM


class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application(self, applicant: User, data: dict) -> Application:
        application = Application(
            applicant_id=applicant.id,
            **data
        )
        self.db.add(application)
        self.db.flush()

        # Record initial DRAFT state
        history = ApplicationStateHistory(
            application_id=application.id,
            from_status=ApplicationStatus.DRAFT,
            to_status=ApplicationStatus.DRAFT,
            changed_by_id=applicant.id,
            notes="Application created"
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
        reviewer_id: str | None = None
    ) -> Application:
        application = self.db.query(Application).filter(
            Application.id == application_id
        ).first()

        if not application:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

        fsm = ApplicationFSM(application, self.db, current_user)

        # Execute transition with enforcement
        if action == "submit":
            fsm.submit(notes)
        elif action == "start_review":
            if not reviewer_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "reviewer_id required")
            fsm.start_review(reviewer_id, notes)
        elif action == "request_information":
            fsm.request_information(notes)
        elif action == "resubmit":
            fsm.resubmit(notes)
        elif action == "complete_review":
            fsm.complete_review(notes)
        elif action == "approve":
            fsm.approve(notes)
        elif action == "reject":
            fsm.reject(notes)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown action: {action}")

        self.db.commit()
        self.db.refresh(application)
        return application

    def get_application(self, application_id: str) -> Application:
        app = self.db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
        return app
