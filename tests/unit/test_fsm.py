import pytest
from fastapi import HTTPException
from app.services.application_fsm import ApplicationFSM
from app.models.application import ApplicationStatus
from app.models.approval_workflow import ApprovalLevel

def test_submit_valid_transition(db, application, applicant_user):
    """Test valid transition from DRAFT to SUBMITTED."""
    initial_version = application.version
    fsm = ApplicationFSM(application, db, applicant_user)
    fsm.submit(notes="Submitting application")
    db.commit()
    db.refresh(application)
    
    assert application.status == ApplicationStatus.SUBMITTED
    assert application.current_level == 1
    assert application.version > initial_version

def test_submit_invalid_status(db, application, applicant_user):
    """Test that submitting an already submitted application fails."""
    application.status = ApplicationStatus.SUBMITTED
    db.commit()
    
    fsm = ApplicationFSM(application, db, applicant_user)
    with pytest.raises(HTTPException) as excinfo:
        fsm.submit()
    assert excinfo.value.status_code == 400
    assert "already submitted" in excinfo.value.detail

def test_submit_not_applicant(db, application, staff_user):
    """Test that only the applicant can submit."""
    fsm = ApplicationFSM(application, db, staff_user)
    
    with pytest.raises(HTTPException) as excinfo:
        fsm.submit()
    assert excinfo.value.status_code == 403
    assert "Only the applicant can submit" in excinfo.value.detail

def test_submit_declaration_not_accepted(db, application, applicant_user):
    """Test that submitting without accepting declaration fails."""
    application.declaration_accepted = False
    db.commit()
    
    fsm = ApplicationFSM(application, db, applicant_user)
    with pytest.raises(HTTPException) as excinfo:
        fsm.submit()
    assert excinfo.value.status_code == 400
    assert "Declaration must be accepted" in excinfo.value.detail

def test_approve_single_level(db, application, staff_user, workflow, applicant_user):
    """Test approval process for a single level workflow."""
    # Setup level
    level = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=1,
        name="Level 1",
        required_approvals=1,
        roles=staff_user.roles
    )
    db.add(level)
    
    # Move to submitted first
    fsm_sub = ApplicationFSM(application, db, applicant_user)
    fsm_sub.submit()
    db.commit()
    db.refresh(application)
    
    initial_version = application.version
    fsm = ApplicationFSM(application, db, staff_user)
    fsm.approve(notes="Approved by staff")
    db.commit()
    db.refresh(application)
    
    assert application.status == ApplicationStatus.APPROVED
    assert application.approved_by == staff_user.id
    assert application.version > initial_version

def test_reject_application(db, application, staff_user, workflow, applicant_user):
    """Test rejecting an application."""
    level = ApprovalLevel(
        workflow_id=workflow.id,
        level_number=1,
        name="Level 1",
        required_approvals=1,
        roles=staff_user.roles
    )
    db.add(level)
    
    fsm_sub = ApplicationFSM(application, db, applicant_user)
    fsm_sub.submit()
    db.commit()
    
    fsm = ApplicationFSM(application, db, staff_user)
    fsm.reject(notes="Rejected due to missing info")
    db.commit()
    db.refresh(application)
    
    assert application.status == ApplicationStatus.REJECTED
    assert application.version > 0
