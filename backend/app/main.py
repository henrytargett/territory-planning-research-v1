"""Main FastAPI application for Territory Planner."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import jobs
from .config import get_settings
from .constants import CORS_ALLOWED_ORIGINS

# Get settings
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Territory Planner...")
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Using LLM model: {settings.crusoe_model}")
    logger.info(f"LLM timeout: {settings.llm_timeout}s")
    logger.info(f"Tavily timeout: {settings.tavily_timeout}s")

    yield

    # Shutdown
    logger.info("Shutting down Territory Planner...")


# Create FastAPI app
app = FastAPI(
    title="Territory Planner",
    description="AI-powered company research and ranking for GPU infrastructure sales",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend (security fix: removed wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "Territory Planner",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "api": "running",
        }
    }



