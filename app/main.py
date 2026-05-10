from fastapi import APIRouter

from app.api.v1 import applications, users_management, auth, documents, workflows, audit_logs

app_routers = APIRouter()

app_routers.include_router(auth.router)
app_routers.include_router(users_management.router)
app_routers.include_router(applications.router)
app_routers.include_router(documents.router)
app_routers.include_router(workflows.router)
app_routers.include_router(audit_logs.router)
