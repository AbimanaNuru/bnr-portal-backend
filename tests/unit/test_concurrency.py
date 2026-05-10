import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.models.application import Application, ApplicationStatus
from app.services.application_fsm import ApplicationFSM

def test_concurrent_access_protection(engine, application, applicant_user):
    """
    Demonstrate that concurrent updates to the same application
    are prevented by optimistic locking (versioning).
    """
    # Create two separate database sessions
    session1 = Session(bind=engine)
    session2 = Session(bind=engine)
    
    try:
        # Load the same application in both sessions
        app1 = session1.query(Application).get(application.id)
        app2 = session2.query(Application).get(application.id)
        
        # User 1 submits the application
        fsm1 = ApplicationFSM(app1, session1, applicant_user)
        fsm1.submit(notes="User 1 submitting")
        session1.commit()
        
        # Now the version in DB has increased
        
        # User 2 tries to perform an action on the OLD version
        # app2 still thinks version is the initial one (0 or 1)
        
        app2.status = ApplicationStatus.APPROVED
        
        # This should fail because the version in DB is now higher than app2's version
        with pytest.raises(StaleDataError):
            session2.commit()
            
    finally:
        session1.close()
        session2.close()
