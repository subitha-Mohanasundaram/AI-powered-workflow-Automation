"""
Database engine and session factory.

Supports both SQLite (development/testing) and PostgreSQL (production).

To migrate from SQLite to PostgreSQL set DATABASE_URL in .env:
  DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

For async use, switch to asyncpg:
  DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
"""
import logging
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _create_engine():
    url = settings.database_url
    kwargs: dict = {}

    if url.startswith("sqlite"):
        # Allow the same connection to be used in multiple threads.
        kwargs["connect_args"] = {"check_same_thread": False}
        # Enable WAL mode for better concurrency under SQLite.
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def set_wal_mode(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine

    if "postgresql" in url:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True   # discard stale connections
        logger.info("Using PostgreSQL database")
        return create_engine(url, **kwargs)

    return create_engine(url, **kwargs)


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a database session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
