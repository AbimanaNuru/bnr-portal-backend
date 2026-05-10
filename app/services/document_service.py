import os
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.documents import ApplicationDocumentRequirement, Document, DocumentTypeDefinition
from app.models.user import User
from app.schemas.documents import DocumentTypeDefinitionCreate, DocumentTypeDefinitionUpdate

UPLOAD_DIR = Path("data/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def create_document_type(self, schema: DocumentTypeDefinitionCreate, current_user: User) -> DocumentTypeDefinition:
        doc_type = DocumentTypeDefinition(
            name=schema.name,
            description=schema.description,
            is_required=schema.is_required,
            is_active=schema.is_active,
            created_by_id=current_user.id,
        )
        self.db.add(doc_type)
        self.db.commit()
        self.db.refresh(doc_type)
        return doc_type

    def list_active_document_types(self) -> List[DocumentTypeDefinition]:
        return self.db.query(DocumentTypeDefinition).filter(DocumentTypeDefinition.is_active == True).all()

    def update_document_type(self, type_id: int, data: DocumentTypeDefinitionUpdate) -> DocumentTypeDefinition:
        doc_type = self.db.query(DocumentTypeDefinition).filter(DocumentTypeDefinition.id == type_id).first()
        if not doc_type:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document type not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(doc_type, field, value)
        self.db.commit()
        self.db.refresh(doc_type)
        return doc_type

    def initialize_application_requirements(self, application: Application) -> List[ApplicationDocumentRequirement]:
        existing = (
            self.db.query(ApplicationDocumentRequirement)
            .filter(ApplicationDocumentRequirement.application_id == application.id)
            .first()
        )
        if existing:
            return (
                self.db.query(ApplicationDocumentRequirement)
                .filter(ApplicationDocumentRequirement.application_id == application.id)
                .all()
            )

        requirements = []
        for dt in self.list_active_document_types():
            req = ApplicationDocumentRequirement(
                application_id=application.id,
                document_type_id=dt.id,
                name_snapshot=dt.name,
                is_required_snapshot=dt.is_required,
                is_satisfied=False,
            )
            requirements.append(req)
            self.db.add(req)

        self.db.commit()
        return requirements

    def get_application_requirements(self, application_id: str) -> List[ApplicationDocumentRequirement]:
        return (
            self.db.query(ApplicationDocumentRequirement)
            .filter(ApplicationDocumentRequirement.application_id == application_id)
            .all()
        )

    def upload_document(
        self,
        application: Application,
        file: UploadFile,
        current_user: User,
        document_type_id: Optional[int] = None,
    ) -> Document:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File exceeds 5MB limit")
        if file_size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")

        if document_type_id is not None:
            req = (
                self.db.query(ApplicationDocumentRequirement)
                .filter(
                    ApplicationDocumentRequirement.application_id == application.id,
                    ApplicationDocumentRequirement.document_type_id == document_type_id,
                )
                .first()
            )
            if not req:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document type for this application")

        new_version = 1
        if document_type_id is not None:
            old_docs = (
                self.db.query(Document)
                .filter(
                    Document.application_id == application.id,
                    Document.document_type_id == document_type_id,
                    Document.is_latest == True,
                )
                .all()
            )
            if old_docs:
                new_version = max(d.version_number for d in old_docs) + 1
                for d in old_docs:
                    d.is_latest = False

        upload_round = "resubmit" if application.status == ApplicationStatus.INFORMATION_REQUESTED else "initial"
        stored_filename = f"{uuid.uuid4()}_{file.filename}"

        with open(UPLOAD_DIR / stored_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

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
            upload_round=upload_round,
        )
        self.db.add(doc)

        if document_type_id is not None:
            req = (
                self.db.query(ApplicationDocumentRequirement)
                .filter(
                    ApplicationDocumentRequirement.application_id == application.id,
                    ApplicationDocumentRequirement.document_type_id == document_type_id,
                )
                .first()
            )
            if req:
                req.is_satisfied = True
                req.satisfied_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_document_path(self, document_id: int, application_id: str) -> Path:
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.application_id == application_id,
        ).first()
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

        file_path = UPLOAD_DIR / str(doc.stored_filename)
        if not file_path.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found on disk")

        return file_path
