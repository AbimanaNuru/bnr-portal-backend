from typing import Optional
from fastapi import APIRouter, Depends, status, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission, require_any_permission
from app.core.security.permissions import Permission
from app.models import User
from app.schemas.application import (
    ApplicationCreate, ApplicationRead,
    StateTransitionRequest, ApplicationUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.application_service import ApplicationService
from app.services.rbac_service import RBACService
from app.services.audit_service import audit
from app.services.application_fsm import ApplicationFSM
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


@router.get("/my", response_model=PaginatedResponse[ApplicationRead])
def my_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ_OWN)),
    db: Session = Depends(get_db),
):
    """Returns only the applications belonging to the authenticated applicant."""
    return ApplicationService(db).get_applications(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        own_only=True,
    )


@router.get("", response_model=PaginatedResponse[ApplicationRead])
def list_all_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ_ALL)),
    db: Session = Depends(get_db),
):
    """Returns all applications. Requires staff-level (APPLICATIONS_TRANSITION) permission."""
    return ApplicationService(db).get_applications(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        own_only=False,
    )


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: str,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ)),
    db: Session = Depends(get_db),
):
    app = ApplicationService(db).get_application(application_id)
    rbac = RBACService(db)

    is_owner = app.applicant_id == current_user.id
    has_read_all = rbac.has_permission_by_name(current_user, Permission.APPLICATIONS_READ_ALL)

    if not (is_owner or current_user.is_superuser or has_read_all):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    # Compute available actions for the current user

    fsm = ApplicationFSM(app, db, current_user)
    app.available_actions = fsm.get_available_actions()

    return app


@router.get("/{application_id}/submission-check")
def submission_check(
    application_id: str,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_READ)),
    db: Session = Depends(get_db),
):
    """
    Dry-run submission validation. Returns a structured checklist so the
    frontend can show exactly what is passing and what is still missing,
    without actually submitting the application.
    """
    app = ApplicationService(db).get_application(application_id)
    rbac = RBACService(db)

    is_owner = app.applicant_id == current_user.id
    has_read_all = rbac.has_permission_by_name(current_user, Permission.APPLICATIONS_READ_ALL)

    if not (is_owner or current_user.is_superuser or has_read_all):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    # --- individual checks ---
    is_draft = app.status.value == "DRAFT"
    declaration_ok = bool(app.declaration_accepted)

    doc_checks = [
        {
            "name": req.name_snapshot,
            "required": req.is_required_snapshot,
            "satisfied": req.is_satisfied,
        }
        for req in app.document_requirements
    ]
    missing_required_docs = [d["name"] for d in doc_checks if d["required"] and not d["satisfied"]]
    documents_ok = len(missing_required_docs) == 0

    ready = is_draft and declaration_ok and documents_ok

    return {
        "application_id": application_id,
        "ready_to_submit": ready,
        "checks": {
            "is_draft": is_draft,
            "declaration_accepted": declaration_ok,
            "all_required_documents_uploaded": documents_ok,
        },
        "documents": doc_checks,
        "missing_required_documents": missing_required_docs,
    }


@router.post("/{application_id}/submit")
@audit(action="APPLICATION_SUBMIT", resource="application")
def submit_application(
    application_id: str,
    request: Request,
    notes: Optional[str] = None,
    current_user: User = Depends(require_permission(Permission.APPLICATIONS_SUBMIT)),
    db: Session = Depends(get_db),
):
    """
    Validate and submit the application in one step.
    - If all checks pass  → submits and returns 200.
    - If anything is missing → returns 422 with a full checklist so the
      frontend can render exactly what still needs to be done.
    """
    service = ApplicationService(db)
    app = service.get_application(application_id)

    if app.applicant_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can submit")

    is_draft = app.status.value == "DRAFT"
    declaration_ok = bool(app.declaration_accepted)

    doc_checks = [
        {
            "name": req.name_snapshot,
            "required": req.is_required_snapshot,
            "satisfied": req.is_satisfied,
        }
        for req in app.document_requirements
    ]
    missing_docs = [d["name"] for d in doc_checks if d["required"] and not d["satisfied"]]
    documents_ok = len(missing_docs) == 0

    if not (is_draft and declaration_ok and documents_ok):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Application is not ready to submit.",
                "ready_to_submit": False,
                "checks": {
                    "is_draft": is_draft,
                    "declaration_accepted": declaration_ok,
                    "all_required_documents_uploaded": documents_ok,
                },
                "documents": doc_checks,
                "missing_required_documents": missing_docs,
            },
        )

    service.transition_state(
        application_id=application_id,
        current_user=current_user,
        action="submit",
        notes=notes,
    )

    request.state.audit_resource_id = application_id
    request.state.audit_new = {"status": "SUBMITTED"}

    return {
        "detail": "Application submitted successfully.",
        "application_id": application_id,
    }

@router.post("/{application_id}/transition")
@audit(action="APPLICATION_TRANSITION", resource="application")
def transition_application(
    application_id: str,
    request_data: StateTransitionRequest,
    request: Request,
    current_user: User = Depends(require_any_permission([
        Permission.APPLICATIONS_TRANSITION,
        Permission.APPLICATIONS_SUBMIT,
        Permission.APPLICATIONS_RESUBMIT,
    ])),
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

    if app.applicant_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can update their application")

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
