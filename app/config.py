"""Configuration settings for the Weight Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    APP_ENV: str = "dev"
    WEIGHT_SERVICE_PORT: int = 8100
    SCALE_PORT: Optional[str] = None  # If None, auto-detect /dev/ttyUSB0-10
    SCALE_BAUDRATE: int = 9600
    SCALE_READ_INTERVAL_MS: int = 10
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

