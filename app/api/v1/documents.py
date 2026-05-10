import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission, get_current_active_user
from app.core.security.permissions import Permission
from app.models.user import User
from app.models.application import Application
from app.models.documents import Document
from app.schemas.documents import (
    DocumentTypeDefinitionCreate,
    DocumentTypeDefinitionRead,
    ApplicationDocumentRequirementRead,
    DocumentRead
)
from app.services.document_service import DocumentService
from app.services.audit_service import audit

router = APIRouter(prefix="/documents", tags=["Documents"])

# Manage Document Type Definitions

@router.post("/types", status_code=status.HTTP_201_CREATED)
@audit(action="DOCUMENT_TYPE_CREATE", resource="document_type")
def create_document_type(
    schema: DocumentTypeDefinitionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DOCUMENTS_MANAGE_TYPES))
):
    """
    Admin ONLY. Defines a new required/optional document type for applications.
    """
    service = DocumentService(db)
    doc_type = service.create_document_type(schema, current_user)
    
    # Audit
    request.state.audit_resource_id = str(doc_type.id)
    request.state.audit_new = {"name": doc_type.name}
    
    return {"detail": "Document type created successfully", "id": str(doc_type.id)}

@router.get("/types", response_model=List[DocumentTypeDefinitionRead])
def list_document_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DOCUMENTS_READ))
):
    """
    List all active document types.
    """
    service = DocumentService(db)
    return service.list_active_document_types()

# View Requirements & Upload

@router.get("/applications/{application_id}/requirements", response_model=List[ApplicationDocumentRequirementRead])
def get_application_requirements(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DOCUMENTS_READ))
):
    """
    Get the exact snapshot of required documents for a specific application.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    if app.applicant_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    service = DocumentService(db)
    return service.get_application_requirements(application_id)

@router.post("/applications/{application_id}/upload")
@audit(action="DOCUMENT_UPLOAD", resource="document")
def upload_application_document(
    application_id: str,
    request: Request,
    file: UploadFile = File(...),
    document_type_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DOCUMENTS_UPLOAD))
):
    """
    Upload a document file to an application.
    Pass `document_type_id` to satisfy a specific requirement.
    Leaves it null if it's a supplementary generic document.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    if app.applicant_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only applicant or admin can upload")

    service = DocumentService(db)
    doc = service.upload_document(app, file, current_user, document_type_id)
    
    # Audit
    request.state.audit_resource_id = str(doc.id)
    request.state.audit_new = {
        "filename": doc.original_filename,
        "application_id": application_id
    }
    
    return {"detail": "Document uploaded successfully", "id": str(doc.id)}

# -------------------------------------------------------------------
# Documents: Download
# -------------------------------------------------------------------

@router.get("/{document_id}/download", response_class=FileResponse)
@audit(action="DOCUMENT_DOWNLOAD", resource="document")
def download_document(
    document_id: int,
    application_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DOCUMENTS_READ))
):
    """
    Download the file bytes for a specific document.
    """
    # Verify access to application
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    if app.applicant_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    service = DocumentService(db)
    file_path = service.get_document_path(document_id, application_id)

    # Audit
    request.state.audit_resource_id = str(document_id)
    request.state.audit_new = {"application_id": application_id}

    # We should get original filename for the download
    doc = db.query(Document).filter(Document.id == document_id).first()

    return FileResponse(
        path=file_path,
        filename=str(doc.original_filename) if doc else "document",
        media_type=str(doc.mime_type) if doc else "application/octet-stream"
    )
