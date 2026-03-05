"""
database.py — SQLAlchemy engine, session factory, and base model.

Provides:
    engine          — The SQLAlchemy engine bound to DATABASE_URL.
    SessionLocal    — A session factory (use as a context manager or dependency).
    Base            — Declarative base class that all ORM models inherit from.
    get_db()        — FastAPI dependency that yields a DB session per request.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# ---------------------------------------------------------------------------
# Engine & session
# ---------------------------------------------------------------------------

# Create the SQLAlchemy engine using the connection string from settings
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # verify connections are alive before using them
)

# Session factory — each call produces a new Session instance
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

# All ORM models should inherit from this Base
Base = declarative_base()

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db():
    """
    Yield a SQLAlchemy session for request-scoped usage.

    Usage in a route:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
