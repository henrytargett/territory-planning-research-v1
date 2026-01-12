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

    try:
        inspector = inspect(engine)

        # Migrate research_jobs table
        job_columns = {col['name']: col for col in inspector.get_columns('research_jobs')}

        migrations = []
        if 'submitted_by' not in job_columns:
            migrations.append("ALTER TABLE research_jobs ADD COLUMN submitted_by VARCHAR(100)")
        if 'total_tavily_credits' not in job_columns:
            migrations.append("ALTER TABLE research_jobs ADD COLUMN total_tavily_credits FLOAT DEFAULT 0.0")
        if 'total_cost_usd' not in job_columns:
            migrations.append("ALTER TABLE research_jobs ADD COLUMN total_cost_usd FLOAT DEFAULT 0.0")
        if 'last_activity_at' not in job_columns:
            migrations.append("ALTER TABLE research_jobs ADD COLUMN last_activity_at DATETIME")
        if 'stalled' not in job_columns:
            migrations.append("ALTER TABLE research_jobs ADD COLUMN stalled INTEGER DEFAULT 0")

        # Migrate companies table
        company_columns = {col['name']: col for col in inspector.get_columns('companies')}

        if 'tavily_credits_used' not in company_columns:
            migrations.append("ALTER TABLE companies ADD COLUMN tavily_credits_used FLOAT DEFAULT 0.0")
        if 'tavily_response_time' not in company_columns:
            migrations.append("ALTER TABLE companies ADD COLUMN tavily_response_time FLOAT")
        if 'llm_tokens_used' not in company_columns:
            migrations.append("ALTER TABLE companies ADD COLUMN llm_tokens_used INTEGER DEFAULT 0")
        if 'llm_response_time' not in company_columns:
            migrations.append("ALTER TABLE companies ADD COLUMN llm_response_time FLOAT")

        # Execute migrations
        if migrations:
            logger.info(f"Running {len(migrations)} database migrations...")
            with engine.connect() as conn:
                for migration in migrations:
                    logger.info(f"  - {migration}")
                    conn.execute(text(migration))
                conn.commit()
            logger.info("All migrations complete")
        else:
            logger.info("Database schema is up to date")

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

