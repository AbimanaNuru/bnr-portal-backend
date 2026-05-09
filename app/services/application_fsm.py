from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models import (
    Application, ApplicationStatus, ApplicationStateHistory,
    User, ApprovalLevel, ApplicationApproval
)

class ApplicationFSM:
    def __init__(self, application: Application, db: Session, current_user: User):
        self.application = application
        self.db = db
        self.current_user = current_user

    def _record_history(self, to_status: ApplicationStatus, notes: str | None = None):
        history = ApplicationStateHistory(
            application_id=self.application.id,
            from_status=self.application.status,
            to_status=to_status,
            changed_by_id=self.current_user.id,
            level_number=self.application.current_level,
            notes=notes,
        )
        self.db.add(history)
        self.db.flush()

    def _get_current_level(self) -> ApprovalLevel:
        level = self.db.query(ApprovalLevel).filter(
            ApprovalLevel.workflow_id == self.application.workflow_id,
            ApprovalLevel.level_number == self.application.current_level
        ).first()
        if not level:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Current approval level not found")
        return level

    def _user_can_approve_at_level(self, level: ApprovalLevel) -> bool:
        # Check if user has any of the roles required for this level
        user_role_ids = {role.id for role in self.current_user.roles}
        level_role_ids = {role.id for role in level.roles}
        return bool(user_role_ids & level_role_ids)

    def _is_level_fully_approved(self, level: ApprovalLevel) -> bool:
        approvals_count = self.db.query(ApplicationApproval).filter(
            ApplicationApproval.application_id == self.application.id,
            ApplicationApproval.level_id == level.id,
            ApplicationApproval.is_approved == True
        ).count()
        return approvals_count >= level.required_approvals  # type: ignore

    def _is_final_level(self, level: ApprovalLevel) -> bool:
        max_level = self.db.query(func.max(ApprovalLevel.level_number)).filter(
            ApprovalLevel.workflow_id == self.application.workflow_id
        ).scalar()
        return level.level_number == max_level

    def submit(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.DRAFT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is already submitted")

        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can submit")

        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
        self.application.current_level = 1  # type: ignore

    def approve(self, notes: str | None = None):
        if self.application.status not in [ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application not in a state that can be approved")

        current_level_obj = self._get_current_level()

        # Check if user has permission at this level
        if not self._user_can_approve_at_level(current_level_obj):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to approve at this level")

        # Check if user already approved this level
        existing_approval = self.db.query(ApplicationApproval).filter(
            ApplicationApproval.application_id == self.application.id,
            ApplicationApproval.level_id == current_level_obj.id,
            ApplicationApproval.approved_by_id == self.current_user.id
        ).first()
        if existing_approval:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You have already approved this level")

        # Record approval
        approval = ApplicationApproval(
            application_id=self.application.id,
            level_id=current_level_obj.id,
            approved_by_id=self.current_user.id,
            notes=notes,
            is_approved=True
        )
        self.db.add(approval)

        # Update status to UNDER_REVIEW if it was SUBMITTED
        if self.application.status == ApplicationStatus.SUBMITTED:
            self.application.status = ApplicationStatus.UNDER_REVIEW  # type: ignore

        # Check if level is fully approved
        if self._is_level_fully_approved(current_level_obj):
            if self._is_final_level(current_level_obj):
                self._record_history(ApplicationStatus.APPROVED, "Final approval reached")
                self.application.status = ApplicationStatus.APPROVED  # type: ignore
            else:
                self._record_history(self.application.status, f"Level {current_level_obj.level_number} fully approved")
                self.application.current_level += 1
                # Status stays UNDER_REVIEW as it moves to next level

    def reject(self, notes: str | None = None):
        current_level_obj = self._get_current_level()
        if not self._user_can_approve_at_level(current_level_obj):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to reject at this level")

        self._record_history(ApplicationStatus.REJECTED, notes)
        self.application.status = ApplicationStatus.REJECTED  # type: ignore

    def request_information(self, notes: str | None = None):
        current_level_obj = self._get_current_level()
        if not self._user_can_approve_at_level(current_level_obj):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized at this level")

        self._record_history(ApplicationStatus.INFORMATION_REQUESTED, notes)
        self.application.status = ApplicationStatus.INFORMATION_REQUESTED  # type: ignore

    def resubmit(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.INFORMATION_REQUESTED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only resubmit if information was requested")

        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can resubmit")

        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
