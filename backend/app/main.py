from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models so SQLAlchemy metadata is registered
import app.models.models  # noqa: F401

# Import routers
from app.api import invoices, projects, entities, dashboard, mapping
from app.api import auth, users, fx, credit_notes

app = FastAPI(
    title="Invoice Tracker API",
    description="Internal invoice tracking and approval platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(invoices.router)
app.include_router(projects.router)
app.include_router(entities.router)
app.include_router(dashboard.router)
app.include_router(mapping.router)
app.include_router(fx.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(credit_notes.router)

@app.get("/")
def root():
    return {"status": "Invoice Tracker API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}