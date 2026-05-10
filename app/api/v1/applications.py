from typing import Optional
from fastapi import APIRouter, Depends, status, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission, get_current_active_user
from app.core.security.permissions import Permission
from app.models import User
from app.schemas.application import (
    ApplicationCreate, ApplicationRead,
    StateTransitionRequest, ApplicationUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.application_service import ApplicationService
from app.services.audit_service import audit

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("/", status_code=status.HTTP_201_CREATED)
@audit(action="APPLICATION_CREATE", resource="application")
def create_application(
    data: ApplicationCreate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_CREATE)),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    app = service.create_application(current_user, data.model_dump())

    request.state.audit_resource_id = str(app.id)
    request.state.audit_new = {
        "institution_name": app.institution_name,
        "institution_type": app.institution_type,
        "status": app.status,
    }

    return {"detail": "Application created successfully", "id": str(app.id)}


@router.get("", response_model=PaginatedResponse[ApplicationRead])
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return ApplicationService(db).get_applications(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
    )


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: str,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ)),
    db: Session = Depends(get_db),
):
    app = ApplicationService(db).get_application(application_id)
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
    db: Session = Depends(get_db),
):
    request.state.audit_resource_id = application_id
    request.state.audit_new = {"action": request_data.action}

    ApplicationService(db).transition_state(
        application_id=application_id,
        current_user=current_user,
        action=request_data.action,
        notes=request_data.notes,
        expected_version=request_data.version,
    )
    return {"detail": "Application transitioned successfully"}


@router.put("/{application_id}")
@audit(action="APPLICATION_UPDATE", resource="application")
def update_application(
    application_id: str,
    data: ApplicationUpdate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_UPDATE)),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    app = service.get_application(application_id)

    if app.version != data.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The application has been modified by another process. Please refresh and try again.",
        )

    request.state.audit_resource_id = str(app.id)
    request.state.audit_old = {
        "title": app.title,
        "institution_name": app.institution_name,
        "status": app.status,
    }

    for field, value in data.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(app, field, value)

    app.version += 1
    db.commit()
    db.refresh(app)

    request.state.audit_new = {
        "title": app.title,
        "institution_name": app.institution_name,
        "status": app.status,
    }

    return {"detail": "Application updated successfully", "id": str(app.id)}
