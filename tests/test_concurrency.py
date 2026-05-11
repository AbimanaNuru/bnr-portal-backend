import pytest
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.models.user import User
from app.models.application import Application, ApplicationStatus, InstitutionType
from app.models.approval_workflow import ApprovalWorkflow
from app.services.application_fsm import ApplicationFSM

def test_concurrent_access_protection(engine):
    """
    Demonstrate that concurrent updates to the same application
    are prevented by optimistic locking (versioning).
    """
    # 1. Setup: Create data in a separate session and COMMIT it
    setup_session = Session(bind=engine)
    
    uid = str(uuid.uuid4())[:8]
    user = User(
        email=f"concurr_{uid}@example.com",
        username=f"concurr_{uid}",
        hashed_password="hashed_password",
        fullname="Concurrency Test User"
    )
    wf = ApprovalWorkflow(name=f"Workflow_{uid}")
    setup_session.add_all([user, wf])
    setup_session.commit()
    
    app = Application(
        applicant_id=user.id,
        workflow_id=wf.id,
        institution_name="Concurrency Bank",
        institution_type=InstitutionType.COMMERCIAL_BANK,
        registration_number="CONC123",
        contact_full_name="John Con",
        contact_title="CTO",
        contact_email="john@example.com",
        contact_phone="123",
        proposed_capital="100",
        primary_products="P",
        target_districts="D",
        title="Concurrency Test",
        declaration_accepted=True,
        status=ApplicationStatus.DRAFT,
        version=1 # Start with version 1
    )
    setup_session.add(app)
    setup_session.commit()
    app_id = app.id
    setup_session.close()

    # 2. Concurrency Test
    session1 = Session(bind=engine)
    session2 = Session(bind=engine)
    
    try:
        # Load the same application in both sessions
        app1 = session1.get(Application, app_id)
        app2 = session2.get(Application, app_id)
        
        assert app1 is not None, "app1 should be found"
        assert app2 is not None, "app2 should be found"
        
        # User 1 submits the application (this increments version)
        fsm1 = ApplicationFSM(app1, session1, user)
        fsm1.submit(notes="User 1 submitting")
        session1.commit()
        
        # Now the version in DB has increased
        
        # User 2 tries to perform an action on the OLD version (app2)
        # app2 still thinks version is 1
        
        app2.status = ApplicationStatus.APPROVED
        
        # This should fail because the version in DB is now higher than app2's version
        with pytest.raises(StaleDataError):
            session2.commit()
            
    finally:
        session1.close()
        session2.close()
