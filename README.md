# BNR Portal Backend

Senior-level, production-ready implementation of RBAC (Role-Based Access Control) and an Application State Machine.

## Key Features
- **RBAC System**: Granular permissions and roles (Users -> Roles -> Permissions).
- **State Machine**: Enforced workflow for Applications (DRAFT -> SUBMITTED -> UNDER_REVIEW -> ...).
- **Service Layer**: Decoupled business logic using ApplicationService and RBACService.
- **FastAPI Integration**: Clean API endpoints with dependency injection and permission enforcement.

## Project Structure
- `app/api/`: API routes.
- `app/core/`: Security and dependencies.
- `app/db/`: Database configuration.
- `app/models/`: SQLAlchemy ORM models.
- `app/schemas/`: Pydantic models for validation.
- `app/services/`: Business logic and State Machine.

## Getting Started
1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `uvicorn app.main:app --reload`
