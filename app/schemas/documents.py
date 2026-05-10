from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Document Type Definitions
# ---------------------------------------------------------

class DocumentTypeDefinitionBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str = Field(default="")
    is_required: bool = Field(default=True)
    is_active: bool = Field(default=True)

class DocumentTypeDefinitionCreate(DocumentTypeDefinitionBase):
    pass

class DocumentTypeDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None

class DocumentTypeDefinitionRead(DocumentTypeDefinitionBase):
    id: int
    created_by_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# Application Document Requirements
# ---------------------------------------------------------

class ApplicationDocumentRequirementRead(BaseModel):
    id: int
    application_id: str
    document_type_id: int
    name_snapshot: str
    is_required_snapshot: bool
    is_satisfied: bool
    satisfied_at: Optional[datetime]

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# Documents
# ---------------------------------------------------------

class DocumentRead(BaseModel):
    id: int
    application_id: str
    document_type_id: Optional[int]
    uploaded_by: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    version_number: int
    is_latest: bool
    upload_round: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}
