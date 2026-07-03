import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models so SQLAlchemy metadata is registered
import app.models.models  # noqa: F401

# Import routers
from app.api import invoices, projects, entities, dashboard, mapping
from app.api import auth, users, fx, credit_notes
from app.api.balances import entity_balance_router, balance_router
from app.api import recurring

logger = logging.getLogger(__name__)


def _run_recurring_job():
    from app.db.database import SessionLocal
    from app.services.recurring_invoice_service import process_due_recurring_invoices
    db = SessionLocal()
    try:
        process_due_recurring_invoices(db)
    except Exception:
        logger.exception("Recurring invoice job failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_recurring_job, "cron", hour=6, minute=0, id="recurring_daily")
    scheduler.start()
    _run_recurring_job()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Invoice Tracker API",
    description="Internal invoice tracking and approval platform",
    version="0.1.0",
    lifespan=lifespan,
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

# Register routers — recurring must come before invoices.router to avoid
# /invoices/{invoice_id} swallowing /invoices/recurring requests.
app.include_router(recurring.router)
app.include_router(invoices.router)
app.include_router(projects.router)
app.include_router(entities.router)
app.include_router(dashboard.router)
app.include_router(mapping.router)
app.include_router(fx.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(credit_notes.router)
app.include_router(entity_balance_router)
app.include_router(balance_router)


@app.get("/")
def root():
    return {"status": "Invoice Tracker API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
