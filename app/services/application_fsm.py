from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Application, ApplicationStatus, ApplicationStateHistory,
    User, ApprovalLevel, ApplicationApproval,
)


class ApplicationFSM:
    def __init__(self, application: Application, db: Session, current_user: User):
        self.application = application
        self.db = db
        self.current_user = current_user

    def _record_history(self, to_status: ApplicationStatus, notes: str | None = None):
        self.db.add(
            ApplicationStateHistory(
                application_id=self.application.id,
                from_status=self.application.status,
                to_status=to_status,
                changed_by_id=self.current_user.id,
                level_number=self.application.current_level,
                notes=notes,
            )
        )
        self.db.flush()

    def _get_current_level(self) -> ApprovalLevel:
        level = self.db.query(ApprovalLevel).filter(
            ApprovalLevel.workflow_id == self.application.workflow_id,
            ApprovalLevel.level_number == self.application.current_level,
        ).first()
        if not level:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Approval level not found")
        return level

    def _user_can_act(self, level: ApprovalLevel) -> bool:
        user_role_ids = {r.id for r in self.current_user.roles}
        return bool(user_role_ids & {r.id for r in level.roles})

    def _level_fully_approved(self, level: ApprovalLevel) -> bool:
        count = self.db.query(ApplicationApproval).filter(
            ApplicationApproval.application_id == self.application.id,
            ApplicationApproval.level_id == level.id,
            ApplicationApproval.is_approved == True,
        ).count()
        return bool(count >= level.required_approvals)  # type: ignore

    def _is_final_level(self, level: ApprovalLevel) -> bool:
        max_level = self.db.query(func.max(ApprovalLevel.level_number)).filter(
            ApprovalLevel.workflow_id == self.application.workflow_id
        ).scalar()
        return bool(level.level_number == max_level)  # type: ignore

    def submit(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.DRAFT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is already submitted")
        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can submit")
        if not self.application.declaration_accepted:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Declaration must be accepted before submitting")

        missing = [
            r.name_snapshot
            for r in self.application.document_requirements
            if r.is_required_snapshot and not r.is_satisfied
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required documents: {', '.join(missing)}",
            )

        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
        self.application.current_level = 1  # type: ignore
        self.application.submitted_at = datetime.now(timezone.utc)  # type: ignore
        self.application.version += 1

    def approve(self, notes: str | None = None):
        if self.application.status not in (ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is not in a reviewable state")

        level = self._get_current_level()

        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to approve at this level")

        already_approved = self.db.query(ApplicationApproval).filter(
            ApplicationApproval.application_id == self.application.id,
            ApplicationApproval.level_id == level.id,
            ApplicationApproval.approved_by_id == self.current_user.id,
        ).first()
        if already_approved:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You have already approved this level")

        self.db.add(
            ApplicationApproval(
                application_id=self.application.id,
                level_id=level.id,
                approved_by_id=self.current_user.id,
                notes=notes,
                is_approved=True,
            )
        )

        if self.application.reviewed_by is None:
            self.application.reviewed_by = self.current_user.id  # type: ignore

        if self.application.status == ApplicationStatus.SUBMITTED:
            self.application.status = ApplicationStatus.UNDER_REVIEW  # type: ignore

        if self._level_fully_approved(level):
            if self._is_final_level(level):
                self._record_history(ApplicationStatus.APPROVED, notes)
                self.application.status = ApplicationStatus.APPROVED  # type: ignore
                self.application.approved_by = self.current_user.id  # type: ignore
            else:
                self._record_history(self.application.status, f"Level {level.level_number} approved")
                self.application.current_level += 1

        self.application.version += 1

    def reject(self, notes: str | None = None):
        level = self._get_current_level()
        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to reject at this level")

        self._record_history(ApplicationStatus.REJECTED, notes)
        self.application.status = ApplicationStatus.REJECTED  # type: ignore
        self.application.version += 1

    def request_information(self, notes: str | None = None):
        level = self._get_current_level()
        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized at this level")

        self._record_history(ApplicationStatus.INFORMATION_REQUESTED, notes)
        self.application.status = ApplicationStatus.INFORMATION_REQUESTED  # type: ignore
        self.application.version += 1

    def resubmit(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.INFORMATION_REQUESTED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only resubmit after information is requested")
        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can resubmit")

        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
        self.application.version += 1
