"""
Database connection utilities. Use DATABASE_URL from settings.
Example: with get_session() as session: ...
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings



def get_database_url() -> str:
    """Return DATABASE_URL; raise if not set."""
    url = settings.DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it in .env.local or the environment."
        )
    return url


def create_db_engine():
    """Create SQLAlchemy engine from DATABASE_URL (postgresql+psycopg://...)."""
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        echo=False,
    )


# Lazy engine and session factory (created on first use when DATABASE_URL is set)
_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    """Return the shared engine; create from DATABASE_URL if needed."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return session factory bound to the shared engine."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager yielding a DB session (commit on exit, rollback on exception)."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
