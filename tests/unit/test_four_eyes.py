import pytest
from fastapi import HTTPException
from app.services.application_fsm import ApplicationFSM
from app.models.application import ApplicationStatus
from app.models.approval_workflow import ApprovalLevel
from app.models.user import Role

def test_reviewer_cannot_approve_same_application(db, application, staff_user, workflow, applicant_user):
    """
    Test the Four-Eyes Principle: 
    The person who reviews an application cannot be the same person who approves it.
    """
    # 1. Setup multi-level workflow
    # Level 1: Technical Review (Reviewer Role)
    # Level 2: Decision (Approver Role)
    
    reviewer_role = Role(name="REVIEWER_ROLE")
    approver_role = Role(name="APPROVER_ROLE")
    db.add_all([reviewer_role, approver_role])
    db.flush()
    
    # Assign both roles to our staff_user for this test case
    staff_user.roles = [reviewer_role, approver_role]
    db.commit()

    level1 = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=1,
        name="Review Level",
        required_approvals=1,
        roles=[reviewer_role]
    )
    level2 = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=2,
        name="Approval Level",
        required_approvals=1,
        roles=[approver_role]
    )
    db.add_all([level1, level2])
    db.commit()

    # 2. Applicant submits application
    fsm_applicant = ApplicationFSM(application, db, applicant_user)
    fsm_applicant.submit()
    db.commit()
    assert application.status == ApplicationStatus.SUBMITTED

    # 3. Staff starts and completes review
    fsm_staff = ApplicationFSM(application, db, staff_user)
    fsm_staff.start_review()
    db.commit()
    assert application.status == ApplicationStatus.UNDER_REVIEW
    assert application.reviewed_by == staff_user.id

    fsm_staff.complete_review()
    db.commit()
    assert application.status == ApplicationStatus.REVIEWED

    # 4. Staff attempts to approve (Decision Level)
    # This should fail because they are the reviewer
    # Note: Even though they have the APPROVER_ROLE, the Four-Eyes logic should block them.
    with pytest.raises(HTTPException) as excinfo:
        fsm_staff.approve(notes="I am the reviewer but I also want to approve")
    
    assert excinfo.value.status_code == 403
    assert "The reviewer cannot be the decision maker" in excinfo.value.detail

def test_different_person_can_approve(db, application, staff_user, workflow, applicant_user):
    """
    Test that a different person can approve after a review is completed.
    """
    # 1. Setup
    reviewer_role = Role(name="REVIEWER_ROLE_2")
    approver_role = Role(name="APPROVER_ROLE_2")
    db.add_all([reviewer_role, approver_role])
    db.flush()
    
    reviewer_user = staff_user # Reuse fixture for reviewer
    reviewer_user.roles = [reviewer_role]
    
    import uuid
    approver_user = type(staff_user)(
        email=f"approver_{uuid.uuid4().hex[:6]}@example.com",
        username=f"approver_{uuid.uuid4().hex[:6]}",
        hashed_password="hashed_password",
        fullname="Approver User",
        roles=[approver_role]
    )
    db.add(approver_user)
    db.commit()

    level1 = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=1,
        name="Review Level",
        required_approvals=1,
        roles=[reviewer_role]
    )
    level2 = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=2,
        name="Approval Level",
        required_approvals=1,
        roles=[approver_role]
    )
    db.add_all([level1, level2])
    db.commit()

    # 2. Flow
    ApplicationFSM(application, db, applicant_user).submit()
    
    fsm_review = ApplicationFSM(application, db, reviewer_user)
    fsm_review.start_review()
    fsm_review.complete_review()
    db.commit()
    
    # 3. Approver approves
    fsm_approve = ApplicationFSM(application, db, approver_user)
    
    # Give approver_user the reviewer_role so they can approve Level 1
    approver_user.roles.append(reviewer_role)
    db.commit()
    
    # Approver approves Level 1
    fsm_approve.approve(notes="I am approving the technical level on behalf of the reviewer")
    db.commit()
    assert application.current_level == 2
    assert application.status == ApplicationStatus.REVIEWED # Not final yet

    # Now approver_user approves Level 2 (Final)
    fsm_approve.approve(notes="Final approval")
    db.commit()
    
    assert application.status == ApplicationStatus.APPROVED
    assert application.approved_by == approver_user.id
