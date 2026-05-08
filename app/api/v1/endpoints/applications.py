from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission, get_current_active_user
from app.models import User
from app.schemas.application import (
    ApplicationCreate, ApplicationRead, 
    StateTransitionRequest, ApplicationUpdate
)
from app.services.application_service import ApplicationService
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("/", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = ApplicationService(db)
    app = service.create_application(current_user, data.model_dump())
    return app


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = ApplicationService(db)
    return service.get_application(application_id)


@router.post("/{application_id}/transition", response_model=ApplicationRead)
def transition_application(
    application_id: str,
    request: StateTransitionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Main endpoint to handle all state transitions with RBAC"""
    
    # Permission check based on action
    action_map = {
        "submit": ("application", "submit"),
        "resubmit": ("application", "submit"),
        "start_review": ("application", "review"),
        "complete_review": ("application", "review"),
        "request_information": ("application", "review"),
        "approve": ("application", "approve"),
        "reject": ("application", "approve"),
    }

    resource, action = action_map.get(request.action, ("application", request.action))
    
    # Apply RBAC manually since it depends on the request body
    rbac = RBACService(db)
    if not rbac.has_permission(current_user, resource, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {resource}:{action}"
        )

    service = ApplicationService(db)
    return service.transition_state(
        application_id=application_id,
        current_user=current_user,
        action=request.action,
        notes=request.notes,
        reviewer_id=request.reviewer_id
    )


@router.put("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Only applicant or reviewer can update in certain states
    # This is a placeholder for actual update logic
    service = ApplicationService(db)
    app = service.get_application(application_id)
    
    # Example logic:
    if current_user.id != app.applicant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant can update")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    
    db.commit()
    db.refresh(app)
    return app
