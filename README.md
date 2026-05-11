# BNR Licensing & Compliance Portal - Backend

A production-ready, senior-level backend implementation for the BNR Bank Licensing & Compliance Portal. This system leverages FastAPI, SQLAlchemy, and a robust state machine to manage complex regulatory workflows with high security and auditability.

## 🚀 Key Features

### 🔐 Security & RBAC
- **Granular RBAC**: A hierarchical Role-Based Access Control system (Users -> Roles -> Permissions).
- **Hardened JWT Auth**: Stateless authentication using secure, short-lived access tokens and refresh tokens.
- **Four-Eyes Principle**: Programmatic enforcement ensuring reviewers cannot be the final approvers for the same application.
- **Data Scoping**: Strict permission guards (e.g., `APPLICATIONS_READ_OWN` vs `APPLICATIONS_READ_ALL`) to prevent unauthorized data access.

### ⚙️ Workflow Engine
- **Application State Machine**: Managed lifecycle (DRAFT → SUBMITTED → UNDER_REVIEW → REVIEWED → APPROVED/REJECTED).
- **Multi-Level Approval**: Support for configurable workflows with multiple review and decision stages.
- **Audit Logging**: Comprehensive, automated tracking of all state transitions and sensitive API actions.

### 📄 Document Management
- **Requirement Tracking**: Automated initialization of document requirements based on institution type.
- **Secure Storage**: Metadata-driven document handling with versioning support.

---

## 📁 Project Structure

```text
app/
├── api/          # FastAPI Route handlers (v1)
├── core/         # Security (JWT, RBAC), configuration, and dependencies
├── db/           # Database session management and base models
├── models/       # SQLAlchemy ORM models (User, Application, Audit, etc.)
├── schemas/      # Pydantic models for request validation and serialization
└── services/     # Core business logic, State Machine (FSM), and RBAC services
scripts/          # Database seeding and migration utilities
tests/            # Unit and integration test suites
```

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL (or SQLite for development)

### 1. Environment Setup
Clone the repository and create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/bnr-portal
FRONTEND_URL=http://localhost:3000

# Security
SECRET_KEY=09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (Resend)
RESEND_API_KEY=re_M9tEex3k_KTCqJ3xxoRxsCWdtXKMEbm86
FROM_EMAIL=buildwithnuru@buildwithnuru.com

# Timezone
TIMEZONE=Africa/Kigali
```
> [!NOTE]
> The `RESEND_API_KEY` provided above is valid for 30 days from implementation.

### 3. Database Initialization
Run the seeding script to initialize roles, permissions, document types, and default workflows:
```bash
python scripts/seed_data.py
```

### 4. Running the Application
Start the FastAPI development server:
```bash
uvicorn app.main:app --reload
```
The API documentation will be available at `http://localhost:8000/docs`.

---

## 🧪 Testing
Run the comprehensive test suite to verify security and workflow logic:
```bash
pytest tests/unit
```

---

## 🛡️ Security & Compliance
- **Regulatory Standards**: Designed to meet strict financial institution compliance requirements.
- **Audit Trail**: Every critical action is recorded with user metadata, IP, and timestamp.
- **Concurrency**: Version-based optimistic locking prevents race conditions during multi-user approvals.
