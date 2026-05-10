from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission, get_current_active_user
from app.core.security.permissions import Permission
from app.models import User
from app.schemas.application import (
    ApplicationCreate, ApplicationRead,
    StateTransitionRequest, ApplicationUpdate
)
from app.services.application_service import ApplicationService
from app.services.rbac_service import RBACService
from app.services.audit_service import audit

router = APIRouter(prefix="/applications", tags=["Applications"])

@router.post("/", status_code=status.HTTP_201_CREATED)
@audit(action="APPLICATION_CREATE", resource="application")
def create_application(
    data: ApplicationCreate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_CREATE)),
    db: Session = Depends(get_db)
):
    service = ApplicationService(db)
    app = service.create_application(current_user, data.model_dump())
    
    # Populate audit data
    request.state.audit_resource_id = str(app.id)
    request.state.audit_new = {
        "title": app.title,
        "institution_type": app.institution_type,
        "status": app.status
    }
    
    return {"detail": "Application created successfully", "id": str(app.id)}

@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: str,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ)),
    db: Session = Depends(get_db)
):
    service = ApplicationService(db)
    app = service.get_application(application_id)
    if app.applicant_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    return app

@router.post("/{application_id}/transition")
@audit(action="APPLICATION_TRANSITION", resource="application")
def transition_application(
    application_id: str,
    request_data: StateTransitionRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_TRANSITION)),
    db: Session = Depends(get_db)
):
    """Main endpoint to handle all state transitions using the dynamic workflow engine"""

    # We rely on the FSM and models to enforce role-based permissions at each level.
    # The RBAC check here is for general access to the transition endpoint.

    # Populate audit data
    request.state.audit_resource_id = str(application_id)
    request.state.audit_new = {"action": request_data.action}

    service = ApplicationService(db)
    service.transition_state(
        application_id=application_id,
        current_user=current_user,
        action=request_data.action,
        notes=request_data.notes
    )
    return {"detail": "Application transitioned successfully", "id": application_id}

@router.put("/{application_id}")
@audit(action="APPLICATION_UPDATE", resource="application")
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_UPDATE)),
    db: Session = Depends(get_db)
):
    # Only applicant or reviewer can update in certain states
    # This is a placeholder for actual update logic
    service = ApplicationService(db)
    app = service.get_application(application_id)

    if current_user.id != app.applicant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can update")

    # Capture old state for audit
    request.state.audit_resource_id = str(app.id)
    request.state.audit_old = {
        "title": app.title,
        "description": app.description,
        "extra_metadata": app.extra_metadata
    }

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app, field, value)

    db.commit()
    db.refresh(app)
    
    # Capture new state for audit
    request.state.audit_new = {
        "title": app.title,
        "description": app.description,
        "extra_metadata": app.extra_metadata
    }
    
    return {"detail": "Application updated successfully", "id": str(app.id)}
