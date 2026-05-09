import os
import warnings

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.main import app_routers

# Suppress SQLAlchemy warnings if necessary
warnings.filterwarnings("ignore", category=UserWarning, module="sqlalchemy")

app = FastAPI(
    title="BNR Portal API",
    summary="Backend API for the BNR Portal platform. Handles application workflows, users, and RBAC.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "defaultModelExpandDepth": 0,
        "docExpansion": "none",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "monokai",
    },
)


def add_cors_middleware(app: FastAPI):
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Add the CORS middleware
add_cors_middleware(app)

# Include all API v1 routes
app.include_router(app_routers, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize all application components when the application starts."""
    print("🚀 Starting BNR Portal Backend API...")
    # Add any necessary async startup logic here (e.g., establishing core connections)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"message": "Welcome to BNR Portal API", "status": "operational"}


if __name__ == "__main__":
    import uvicorn

    # Optional: read port from env, default 8000
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
