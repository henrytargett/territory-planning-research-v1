"""Database connection and session management."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
import logging

from .config import get_settings
from .models import Base

logger = logging.getLogger(__name__)

settings = get_settings()

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables and run migrations."""
    Base.metadata.create_all(bind=engine)
    
    # Migration: Add submitted_by column if it doesn't exist
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('research_jobs')]
        
        if 'submitted_by' not in columns:
            logger.info("Adding submitted_by column to research_jobs table...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE research_jobs ADD COLUMN submitted_by VARCHAR(100)"))
                conn.commit()
            logger.info("Migration complete: submitted_by column added")
    except Exception as e:
        logger.warning(f"Migration check failed (this is OK for new databases): {e}")


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

