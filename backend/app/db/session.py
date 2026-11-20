"""
Module: session.py
Purpose: Database engine and session lifecycle manager for SQLite/PostgreSQL.
Standards: Rule 1 (Relational Integrity), Rule 2 (ACID Safety), Rule 3 (Concise & Modular).
"""
import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

load_dotenv()

# Compute absolute path to the data directory relative to this module file.
# This prevents silent creation of a new empty DB when the server starts
# from a different working directory.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default to local SQLite database (absolute path), or cloud PostgreSQL if configured.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DATA_DIR / 'jobs.db'}")

engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif DATABASE_URL.startswith(("postgresql", "postgres")):
    # Enterprise PostgreSQL Connection Pooling & Health Pre-ping (Bug 28)
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Enable WAL Mode, Busy Timeout, Synchronous Normal, and Foreign Keys in SQLite (Bug 27)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    """Yields a thread-safe database session with automatic transaction cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Creates all database tables defined in models if they do not exist."""
    Base.metadata.create_all(bind=engine)
