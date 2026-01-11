"""
ARCHON API Configuration

Environment-based settings for the FastAPI backend.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ARCHON PRIME API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://archon:archon@localhost:5432/archon"
    DATABASE_ECHO: bool = False

    # JWT Authentication
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (for MT5 credentials)
    MASTER_ENCRYPTION_KEY: str = "your-master-encryption-key-32chars"
    ENCRYPTION_SALT: str = "archon-salt-value"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"]

    # MT5 Connection Pool
    MT5_POOL_MAX_CONNECTIONS: int = 100
    MT5_POOL_IDLE_TIMEOUT_SEC: int = 300
    MT5_RECONNECT_DELAY_SEC: int = 5
    MT5_MAX_RECONNECT_ATTEMPTS: int = 10

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Redis (optional, for sessions/caching)
    REDIS_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
