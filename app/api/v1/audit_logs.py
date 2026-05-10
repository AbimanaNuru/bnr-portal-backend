import math
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, asc, desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security.dependencies import require_permission
from app.core.security.permissions import Permission
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogSchema, PaginatedResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

# Whitelist of columns allowed for sorting to prevent SQL injection
_SORTABLE_COLUMNS = {
    "created_at": AuditLog.created_at,
    "action": AuditLog.action,
    "resource": AuditLog.resource,
    "user_email": AuditLog.user_email,
    "user_role": AuditLog.user_role,
    "status": AuditLog.status,
    "ip_address": AuditLog.ip_address,
}

@router.get(
    "",
    response_model=PaginatedResponse[AuditLogSchema],
    summary="Get all audit logs (Admin only)",
)
async def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_permission(Permission.AUDIT_READ)),
    search: Optional[str] = Query(None, description="Search across email, action, resource, or IP"),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(AuditLog)

    # Apply keyword search
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.user_email.ilike(like),
                AuditLog.user_full_name.ilike(like),
                AuditLog.action.ilike(like),
                AuditLog.resource.ilike(like),
                AuditLog.resource_id.ilike(like),
                AuditLog.ip_address.ilike(like),
            )
        )

    # Apply exact filters
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.resource == resource)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if status:
        query = query.filter(AuditLog.status == status.lower())

    # Apply date range filtering
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    total_count = query.count()

    # Apply sorting
    sort_column = _SORTABLE_COLUMNS.get(sort_by, AuditLog.created_at)
    order_fn = desc if sort_order.lower() == "desc" else asc
    query = query.order_by(order_fn(sort_column))

    # Apply pagination
    offset = (page - 1) * page_size
    logs = query.offset(offset).limit(page_size).all()
    total_pages = math.ceil(total_count / page_size) if total_count else 1

    return PaginatedResponse(
        items=[AuditLogSchema.model_validate(log) for log in logs],
        message="Audit logs retrieved successfully",
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        page_size=page_size,
    )

@router.get(
    "/{log_id}",
    response_model=AuditLogSchema,
    summary="Get single audit log details (Admin only)",
)
async def get_audit_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(require_permission(Permission.AUDIT_READ)),
):
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return AuditLogSchema.model_validate(log)
