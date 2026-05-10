from __future__ import annotations

import asyncio
import logging
import re
from functools import wraps
from typing import Any, Optional

from fastapi import Request
from user_agents import parse as ua_parse

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
from fastapi.concurrency import run_in_threadpool

# Redact sensitive information from logs
SENSITIVE_FIELDS = re.compile(
    r"(password|passwd|secret|token|access_token|refresh_token|api_key|apikey|otp|cvv|pin)",
    re.IGNORECASE,
)
REDACTION_TEXT = "*** REDACTED ***"

def _scrub_sensitive_data(data: Any) -> Any:
    """Recursively redacts sensitive keys from dictionaries and lists."""
    if isinstance(data, dict):
        return {
            k: (REDACTION_TEXT if SENSITIVE_FIELDS.search(k) else _scrub_sensitive_data(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_scrub_sensitive_data(item) for item in data]
    return data

def _get_ip_address(request: Request) -> Optional[str]:
    """Extracts the client's IP address, accounting for proxies."""
    if x_forwarded_for := request.headers.get("x-forwarded-for"):
        return x_forwarded_for.split(",")[0].strip()
    if x_real_ip := request.headers.get("x-real-ip"):
        return x_real_ip.strip()
    return request.client.host if request.client else None

async def _persist_audit_log(data: dict) -> None:
    """Writes the audit record to the database in a background task."""
    db = SessionLocal()
    try:
        ua_string = data.get("user_agent") or ""
        ua = ua_parse(ua_string) if ua_string else None

        device = "Other"
        if ua:
            if ua.is_mobile: device = "Mobile"
            elif ua.is_tablet: device = "Tablet"
            elif ua.is_pc: device = "Desktop"

        log_entry = AuditLog(
            user_id=data.get("user_id"),
            user_email=data.get("user_email"),
            user_role=data.get("user_role"),
            user_full_name=data.get("user_full_name"),
            action=data["action"],
            resource=data.get("resource"),
            resource_id=str(data["resource_id"]) if data.get("resource_id") else None,
            status=data.get("status", "success"),
            old_data=_scrub_sensitive_data(data.get("old_data")),
            new_data=_scrub_sensitive_data(data.get("new_data")),
            extra=data.get("extra"),
            ip_address=data.get("ip"),
            user_agent=ua_string or None,
            browser=ua.browser.family if ua else None,
            browser_version=ua.browser.version_string if ua else None,
            os=ua.os.family if ua else None,
            os_version=ua.os.version_string if ua else None,
            device=device,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Audit Log Failure: {data.get('action')} - {str(e)}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def audit(action: str, resource: str):
    """
    Decorator to automatically log API actions.
    Expects 'request: Request' and optionally 'current_user' in function arguments.
    """
    def decorator(func):
        import inspect

        is_coroutine = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            user = kwargs.get("current_user")

            # Extract actor information
            actor_data = {"user_id": None, "user_email": None, "user_full_name": None, "user_role": None}
            if user:
                actor_data["user_id"] = getattr(user, "id", None)
                actor_data["user_email"] = getattr(user, "email", getattr(user, "username", None))
                actor_data["user_full_name"] = getattr(user, "fullname", None)

                roles = getattr(user, "roles", None)
                if roles and isinstance(roles, list):
                    actor_data["user_role"] = roles[0].name
                else:
                    actor_data["user_role"] = getattr(user, "role", None)

            ip = _get_ip_address(request) if request else None
            ua = request.headers.get("user-agent", "") if request else ""

            try:
                if is_coroutine:
                    result = await func(*args, **kwargs)
                else:
                    result = await run_in_threadpool(func, *args, **kwargs)

                audit_payload = {
                    "action": action,
                    "resource": resource,
                    **actor_data,
                    "ip": ip,
                    "user_agent": ua,
                    "old_data": getattr(request.state, "audit_old", None) if request else None,
                    "new_data": getattr(request.state, "audit_new", None) if request else None,
                    "resource_id": getattr(request.state, "audit_resource_id", None) if request else None,
                    "status": "success",
                }
                asyncio.create_task(_persist_audit_log(audit_payload))
                return result

            except Exception as e:
                error_payload = {
                    "action": action,
                    "resource": resource,
                    **actor_data,
                    "status": "failure",
                    "extra": {"error": str(e)},
                    "ip": ip,
                    "user_agent": ua,
                }
                asyncio.create_task(_persist_audit_log(error_payload))
                raise e

        return wrapper
    return decorator
