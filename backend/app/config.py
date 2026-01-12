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
    
    model_config = {
        "env_file": ["../.env", ".env"],  # Check parent dir first, then current
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

