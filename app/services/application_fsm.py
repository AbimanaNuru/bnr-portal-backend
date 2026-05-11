from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

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
        max_level_num = self.db.query(func.max(ApprovalLevel.level_number)).filter(
            ApprovalLevel.workflow_id == self.application.workflow_id
        ).scalar() or 1

        if self.application.current_level > max_level_num:
            self.application.current_level = max_level_num
            self.db.flush()

        level = (
            self.db.query(ApprovalLevel)
            .options(selectinload(ApprovalLevel.roles))
            .filter(
                ApprovalLevel.workflow_id == self.application.workflow_id,
                ApprovalLevel.level_number == self.application.current_level,
            )
            .first()
        )
        if not level:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Approval level not found after adaptation")
        return level

    def _user_can_act(self, level: ApprovalLevel) -> bool:
        if self.current_user.is_superuser:
            return True

        user_role_ids = {r.id for r in self.current_user.roles}
        level_role_ids = {r.id for r in level.roles}
        return bool(user_role_ids & level_role_ids)

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

    def approve(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.REVIEWED:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Application must be in REVIEWED state (review completed) before approval"
            )

        # Enforcement: Reviewer cannot be the Approver
        if self.current_user.id == self.application.reviewed_by:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Enforcement Rule: The reviewer cannot be the decision maker for the same application."
            )

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
        self.db.flush()

        if self._level_fully_approved(level):
            if self._is_final_level(level):
                self._record_history(ApplicationStatus.APPROVED, notes)
                self.application.status = ApplicationStatus.APPROVED  # type: ignore
                self.application.approved_by = self.current_user.id  # type: ignore
            else:
                # Promotion to next level
                self.application.current_level += 1
                self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
                self.application.reviewed_by = None  # type: ignore
                self._record_history(ApplicationStatus.SUBMITTED, f"Level {level.level_number} fully approved. Promoted to Level {level.level_number + 1}")


    def reject(self, notes: str | None = None):
        if self.application.status not in (ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REVIEWED):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is not in a rejectable state")

        level = self._get_current_level()
        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to reject at this level")

        self._record_history(ApplicationStatus.REJECTED, notes)
        self.application.status = ApplicationStatus.REJECTED  # type: ignore
        self.application.approved_by = self.current_user.id  # type: ignore

    def request_information(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.UNDER_REVIEW:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Information can only be requested during review")

        level = self._get_current_level()
        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized at this level")

        self._record_history(ApplicationStatus.INFORMATION_REQUESTED, notes)
        self.application.status = ApplicationStatus.INFORMATION_REQUESTED  # type: ignore
        self.application.reviewer_notes = notes  # type: ignore

    def resubmit(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.INFORMATION_REQUESTED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only resubmit after information is requested")
        if self.current_user.id != self.application.applicant_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can resubmit")

        self._record_history(ApplicationStatus.SUBMITTED, notes)
        self.application.status = ApplicationStatus.SUBMITTED  # type: ignore
        self.application.reviewed_by = None  # type: ignore

    def start_review(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.SUBMITTED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is not in SUBMITTED state")

        level = self._get_current_level()
        if not self._user_can_act(level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized to start review")

        self._record_history(ApplicationStatus.UNDER_REVIEW, notes)
        self.application.status = ApplicationStatus.UNDER_REVIEW  # type: ignore
        self.application.reviewed_by = self.current_user.id  # type: ignore

    def complete_review(self, notes: str | None = None):
        if self.application.status != ApplicationStatus.UNDER_REVIEW:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Application is not in UNDER_REVIEW state")

        if self.application.reviewed_by != self.current_user.id:
             raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the assigned reviewer can complete the review")

        self._record_history(ApplicationStatus.REVIEWED, notes)
        self.application.status = ApplicationStatus.REVIEWED  # type: ignore

    def get_available_actions(self) -> list[str]:
        actions = []

        # 1. Applicant actions
        if self.current_user.id == self.application.applicant_id:
            if self.application.status == ApplicationStatus.DRAFT:
                actions.append("submit")
            elif self.application.status == ApplicationStatus.INFORMATION_REQUESTED:
                actions.append("resubmit")

        # 2. Staff actions
        # Approved/Rejected applications have no more actions
        if self.application.status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED):
            return actions

        try:
            level = self._get_current_level()
            can_act = self._user_can_act(level)
        except Exception:
            can_act = False
            level = None

        if can_act and level:
            if self.application.status == ApplicationStatus.SUBMITTED:
                actions.append("start_review")

            if self.application.status == ApplicationStatus.UNDER_REVIEW:
                if self.application.reviewed_by == self.current_user.id:
                    actions.append("complete_review")
                    actions.append("request_info")

                # Rejection can happen at UNDER_REVIEW
                actions.append("reject")

            if self.application.status == ApplicationStatus.REVIEWED:
                # Reviewer cannot approve (Four-Eyes Principle)
                if self.application.reviewed_by != self.current_user.id:
                    # Check if already approved at this level
                    already_approved = self.db.query(ApplicationApproval).filter(
                        ApplicationApproval.application_id == self.application.id,
                        ApplicationApproval.level_id == level.id,
                        ApplicationApproval.approved_by_id == self.current_user.id,
                    ).first()
                    if not already_approved:
                        actions.append("approve")
                actions.append("reject")

        return actions
