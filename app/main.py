from fastapi import FastAPI
from app.api.v1.endpoints import applications

app = FastAPI(title="BNR Portal API")

app.include_router(applications.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to BNR Portal API"}
