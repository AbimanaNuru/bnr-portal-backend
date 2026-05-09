from fastapi import APIRouter

from app.api.v1 import applications, users_management, auth, documents

app_routers = APIRouter()

# ── Route Inclusions ──────────────────────────────────────────────────────────

app_routers.include_router(auth.router)
app_routers.include_router(users_management.router)
app_routers.include_router(applications.router)
app_routers.include_router(documents.router)
