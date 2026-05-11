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
SECRET_KEY=generate-a-long-random-hex-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (Resend)
RESEND_API_KEY= You can find key in design document
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

Run the comprehensive test suite to verify security, concurrency, and workflow logic. All tests are designed for a high-integrity environment.

```bash
# Run all tests with verbose output
pytest tests/ -v

# Specific verification paths:
pytest tests/test_state_machine.py     # Valid/invalid transitions + edge cases
pytest tests/test_rbac_enforcement.py  # RBAC boundary tests per role
pytest tests/test_four_eyes.py         # Four-Eyes principle enforcement
pytest tests/test_concurrency.py       # Optimistic locking (simultaneous writers)
```

---

## 🛡️ Security & Compliance

This implementation is architected for strict financial regulatory compliance:

- **Four-Eyes Principle**: Technically enforced at the service level. A user assigned as a `reviewer` for an application is strictly prohibited from being the final decision-maker (`approver`) for that same application.
- **Optimistic Concurrency Control**: Uses a `version` column in the database to prevent race conditions. If two staff members attempt to approve the same application simultaneously, the second attempt will be safely rejected with a `StaleDataError`.
- **Immutable Audit Trail**: Every critical action—including login attempts, state changes, and permission updates—is recorded with a tamper-resistant asynchronous audit logging system.
- **Data Scoping**: Access to application data is scoped at the API layer. Applicants can only access their own submissions, while authorized staff can access the full registry according to their permission levels.
