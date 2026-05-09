import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import get_current_user
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

router = APIRouter(prefix="/documents", tags=["Documents"])



# Manage Document Type Definitions

@router.post("/types", response_model=DocumentTypeDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_document_type(
    schema: DocumentTypeDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin ONLY. Defines a new required/optional document type for applications.
    """
    if not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can define document types")

    service = DocumentService(db)
    return service.create_document_type(schema, current_user)


@router.get("/types", response_model=List[DocumentTypeDefinitionRead])
def list_document_types(
    institution_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all active document types.
    Can filter by institution_type to see what a specific institution needs.
    """
    service = DocumentService(db)
    return service.list_active_document_types(institution_type)


# View Requirements & Upload

@router.get("/applications/{application_id}/requirements", response_model=List[ApplicationDocumentRequirementRead])
def get_application_requirements(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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


@router.post("/applications/{application_id}/upload", response_model=DocumentRead)
def upload_application_document(
    application_id: str,
    file: UploadFile = File(...),
    document_type_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    return service.upload_document(app, file, current_user, document_type_id)


# -------------------------------------------------------------------
# Documents: Download
# -------------------------------------------------------------------

@router.get("/{document_id}/download", response_class=FileResponse)
def download_document(
    document_id: int,
    application_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

    # We should get original filename for the download
    doc = db.query(Document).filter(Document.id == document_id).first()

    return FileResponse(
        path=file_path,
        filename=str(doc.original_filename) if doc else "document",
        media_type=str(doc.mime_type) if doc else "application/octet-stream"
    )
