"""
Configuration settings for SentinelZ AI Backend.
Supports environment variables and .env file loading.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelZ AI Backend"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api"
    
    # Development CORS: Restrict to local frontend origins by default.
    # Configurable via environment variable (e.g., CORS_ORIGINS=["http://localhost:3000"])
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # IBM Z integration configuration (placeholder until real credentials are provided)
    ibm_z_host: str = ""
    ibm_z_api_key: str = ""
    ibm_z_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
