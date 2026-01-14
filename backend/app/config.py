"""Configuration management for the Territory Planner app."""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Crusoe Cloud API
    crusoe_api_key: str
    crusoe_api_base_url: str = "https://api.crusoe.ai/v1/"
    crusoe_model: str = "meta-llama/Llama-3.3-70B-Instruct"

    # Tavily Search API
    tavily_api_key: str

    # Database
    database_url: str = "sqlite:///./data/territory_planner.db"

    # App Settings
    app_env: str = "development"
    log_level: str = "INFO"

    # API Timeouts (seconds) - can be overridden via environment variables
    tavily_timeout: float = 30.0
    llm_timeout: float = 60.0

    # Retry Configuration
    max_retries: int = 3
    retry_base_delay: float = 2.0

    # Rate Limiting
    delay_between_companies: float = 1.0

    # Parallel Processing
    enable_batch_processing: bool = True  # Use parallel batch processing (much faster)
    batch_size: int = 50  # Number of concurrent LLM requests (start conservative)
    tavily_concurrency: int = 100  # Number of concurrent Tavily searches

    # Tavily Caching & Validation
    enable_tavily_caching: bool = True  # Cache Tavily data to avoid re-fetching
    tavily_validation_enabled: bool = True  # Validate data quality before caching
    tavily_validation_threshold: float = 0.6  # Min confidence to accept data
    tavily_max_validation_retries: int = 2  # Retry fetches if validation fails

    # Job Health Monitoring
    job_stall_threshold: int = 300  # Seconds

    model_config = {
        "env_file": ["../.env", ".env"],  # Check parent dir first, then current
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

