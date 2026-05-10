import os
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status

from app.models.documents import (
    DocumentTypeDefinition,
    ApplicationDocumentRequirement,
    Document
)
from app.models.application import Application, ApplicationStatus
from app.models.user import User
from app.schemas.documents import DocumentTypeDefinitionCreate, DocumentTypeDefinitionUpdate

# Directory to store uploaded files locally
UPLOAD_DIR = Path("data/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # Admin: Document Type Definitions
    # ---------------------------------------------------------

    def create_document_type(self, schema: DocumentTypeDefinitionCreate, current_user: User) -> DocumentTypeDefinition:
        doc_type = DocumentTypeDefinition(
            name=schema.name,
            description=schema.description,
            is_required=schema.is_required,
            is_active=schema.is_active,
            created_by_id=current_user.id
        )
        self.db.add(doc_type)
        self.db.commit()
        self.db.refresh(doc_type)
        return doc_type

    def list_active_document_types(self) -> List[DocumentTypeDefinition]:
        query = self.db.query(DocumentTypeDefinition).filter(DocumentTypeDefinition.is_active == True)
        return query.all()

    # ---------------------------------------------------------
    # Application Requirements Snapshot
    # ---------------------------------------------------------

    def initialize_application_requirements(self, application: Application) -> List[ApplicationDocumentRequirement]:
        """
        Takes a snapshot of currently active DocumentTypeDefinitions that match
        this application's institution_type and creates requirements.
        Called when an application is first created/submitted.
        """
        # Check if already initialized to prevent duplicates
        existing = self.db.query(ApplicationDocumentRequirement).filter(
            ApplicationDocumentRequirement.application_id == application.id
        ).first()
        if existing:
            return self.db.query(ApplicationDocumentRequirement).filter(
                ApplicationDocumentRequirement.application_id == application.id
            ).all()

        active_types = self.list_active_document_types()
        requirements = []

        for dt in active_types:
            req = ApplicationDocumentRequirement(
                application_id=application.id,
                document_type_id=dt.id,
                name_snapshot=dt.name,
                is_required_snapshot=dt.is_required,
                is_satisfied=False
            )
            requirements.append(req)
            self.db.add(req)

        self.db.commit()
        return requirements

    def get_application_requirements(self, application_id: str) -> List[ApplicationDocumentRequirement]:
        return self.db.query(ApplicationDocumentRequirement).filter(
            ApplicationDocumentRequirement.application_id == application_id
        ).all()

    # ---------------------------------------------------------
    # File Upload and Versioning
    # ---------------------------------------------------------

    def upload_document(
        self,
        application: Application,
        file: UploadFile,
        current_user: User,
        document_type_id: Optional[int] = None
    ) -> Document:
        # 1. Validate file size (reading to EOF, then seeking back)
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File exceeds 5MB limit")
        if file_size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")

        # 2. Check if document_type_id is valid for this application
        if document_type_id is not None:
            req = self.db.query(ApplicationDocumentRequirement).filter(
                ApplicationDocumentRequirement.application_id == application.id,
                ApplicationDocumentRequirement.document_type_id == document_type_id
            ).first()
            if not req:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document type for this application")

        # 3. Handle Versioning
        new_version = 1
        if document_type_id is not None:
            # Mark previous versions as not latest
            old_docs = self.db.query(Document).filter(
                Document.application_id == application.id,
                Document.document_type_id == document_type_id,
                Document.is_latest == True
            ).all()

            if old_docs:
                new_version = max(d.version_number for d in old_docs) + 1
                for d in old_docs:
                    d.is_latest = False

        # Determine Upload Round
        # "initial" if DRAFT, "resubmit_1" etc. Based on the state history could be complex.
        # We'll default to "initial" unless status is INFORMATION_REQUESTED
        upload_round = "initial"
        if application.status == ApplicationStatus.INFORMATION_REQUESTED:
            upload_round = "resubmit" # simplified

        # 4. Save to Disk
        stored_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / stored_filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 5. Create Database Record
        doc = Document(
            application_id=application.id,
            document_type_id=document_type_id,
            uploaded_by=current_user.id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_size_bytes=file_size,
            mime_type=file.content_type or "application/octet-stream",
            version_number=new_version,
            is_latest=True,
            upload_round=upload_round
        )
        self.db.add(doc)

        # 6. Update Requirement to satisfied
        if document_type_id is not None:
            req = self.db.query(ApplicationDocumentRequirement).filter(
                ApplicationDocumentRequirement.application_id == application.id,
                ApplicationDocumentRequirement.document_type_id == document_type_id
            ).first()
            if req:
                req.is_satisfied = True
                req.satisfied_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(doc)
        return doc

    # ---------------------------------------------------------
    # Download
    # ---------------------------------------------------------

    def get_document_path(self, document_id: int, application_id: str) -> Path:
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.application_id == application_id
        ).first()

        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

        file_path = UPLOAD_DIR / doc.stored_filename
        if not file_path.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found on disk")

        return file_path
