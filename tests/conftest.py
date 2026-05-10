import pytest
import os
import uuid
os.environ["TESTING"] = "True"
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base
from app.models.user import User, Role, Permission
from app.models.application import Application, ApplicationStatus, InstitutionType
from app.models.approval_workflow import ApprovalWorkflow, ApprovalLevel
from app.models.documents import ApplicationDocumentRequirement

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def applicant_user(db: Session):
    uid = str(uuid.uuid4())[:8]
    user = User(
        email=f"applicant_{uid}@example.com",
        username=f"applicant_{uid}",
        hashed_password="hashed_password",
        fullname="Test Applicant"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def staff_user(db: Session):
    uid = str(uuid.uuid4())[:8]
    role = Role(name=f"STAFF_{uid}")
    user = User(
        email=f"staff_{uid}@example.com",
        username=f"staff_{uid}",
        hashed_password="hashed_password",
        fullname="Test Staff",
        roles=[role]
    )
    db.add_all([role, user])
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def workflow(db: Session):
    wf = ApprovalWorkflow(name=f"Workflow_{uuid.uuid4()}")
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf

@pytest.fixture
def application(db: Session, applicant_user: User, workflow: ApprovalWorkflow):
    app = Application(
        applicant_id=applicant_user.id,
        workflow_id=workflow.id,
        institution_name="Test Bank",
        institution_type=InstitutionType.COMMERCIAL_BANK,
        registration_number="12345",
        contact_full_name="John Doe",
        contact_title="CEO",
        contact_email="john@example.com",
        contact_phone="123456789",
        proposed_capital="1000000",
        primary_products="Banking",
        target_districts="Central",
        title="Test Application",
        declaration_accepted=True,
        status=ApplicationStatus.DRAFT
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app
