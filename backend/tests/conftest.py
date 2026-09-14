import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.models import User


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database per test.

    None of the register/aging/filtering logic under test relies on
    Postgres-specific SQL (bucket filtering is done with plain date-range
    comparisons in Python, not CURRENT_DATE arithmetic), so SQLite is a
    faithful stand-in and keeps the suite fast and dependency-free.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def actor(db_session):
    user = User(
        email="finance@example.com",
        full_name="Finance Tester",
        role="admin",
        must_reset_password=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
