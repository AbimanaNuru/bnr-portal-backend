from datetime import datetime
from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, ConfigDict
from uuid import UUID

T = TypeVar("T")

class AuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    user_full_name: Optional[str] = None
    
    action: str
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    status: str
    
    old_data: Optional[dict] = None
    new_data: Optional[dict] = None
    extra: Optional[dict] = None
    
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    device: Optional[str] = None
    
    created_at: datetime

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    message: str = "Success"
