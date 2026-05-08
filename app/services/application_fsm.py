from transitions import Machine
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import Application, ApplicationStatus, ApplicationStateHistory, User

class ApplicationFSM:
    states = [
        'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'INFORMATION_REQUESTED',
        'REVIEWED', 'APPROVED', 'REJECTED'
    ]

    transitions = [
        {'trigger': 'submit', 'source': 'DRAFT', 'dest': 'SUBMITTED'},
        {'trigger': 'start_review', 'source': 'SUBMITTED', 'dest': 'UNDER_REVIEW'},
        {'trigger': 'request_information', 'source': 'UNDER_REVIEW', 'dest': 'INFORMATION_REQUESTED'},
        {'trigger': 'resubmit', 'source': 'INFORMATION_REQUESTED', 'dest': 'SUBMITTED'},
        {'trigger': 'complete_review', 'source': 'UNDER_REVIEW', 'dest': 'REVIEWED'},
        {'trigger': 'approve', 'source': 'REVIEWED', 'dest': 'APPROVED'},
        {'trigger': 'reject', 'source': 'REVIEWED', 'dest': 'REJECTED'},
    ]

    def __init__(self, application: Application, db: Session, current_user: User):
        self.application = application
        self.db = db
        self.current_user = current_user
        self.machine = Machine(model=self, states=self.states, transitions=self.transitions,
                               initial=application.status.value)

    def _record_history(self, to_status: ApplicationStatus, notes: str | None = None):
        history = ApplicationStateHistory(
            application_id=self.application.id,
            from_status=self.application.status,
            to_status=to_status,
            changed_by_id=self.current_user.id,
            reviewer_id=self.application.reviewer_id,
            decision_maker_id=self.application.decision_maker_id,
            notes=notes,
        )
        self.db.add(history)
        self.db.flush()

    # Enforce RBAC + Business Rules
    def submit(self, notes: str | None = None):
        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can submit")
        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED

    def start_review(self, reviewer_id: str, notes: str | None = None):
        # Enforcement: Reviewer must be different from applicant
        if reviewer_id == self.application.applicant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reviewer cannot be the applicant")
        self.application.reviewer_id = reviewer_id
        self._record_history(ApplicationStatus.UNDER_REVIEW, notes)
        self.application.status = ApplicationStatus.UNDER_REVIEW

    def complete_review(self, notes: str | None = None):
        self._record_history(ApplicationStatus.REVIEWED, notes)
        self.application.status = ApplicationStatus.REVIEWED

    def approve(self, notes: str | None = None):
        if self.current_user.id == self.application.reviewer_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 
                              "Reviewer cannot be the decision maker (Enforcement rule)")
        self.application.decision_maker_id = self.current_user.id
        self._record_history(ApplicationStatus.APPROVED, notes)
        self.application.status = ApplicationStatus.APPROVED

    def reject(self, notes: str | None = None):
        if self.current_user.id == self.application.reviewer_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 
                              "Reviewer cannot be the decision maker")
        self.application.decision_maker_id = self.current_user.id
        self._record_history(ApplicationStatus.REJECTED, notes)
        self.application.status = ApplicationStatus.REJECTED

    def request_information(self, notes: str | None = None):
        self._record_history(ApplicationStatus.INFORMATION_REQUESTED, notes)
        self.application.status = ApplicationStatus.INFORMATION_REQUESTED

    def resubmit(self, notes: str | None = None):
        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can resubmit")
        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED
