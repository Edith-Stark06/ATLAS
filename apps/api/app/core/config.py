from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root — apps/api/app/core/config.py -> up 4 levels
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application settings, loaded from environment / repo-root .env."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    database_url: str = "postgresql+psycopg://atlas:atlas_dev_password@localhost:5432/atlas"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Comma-separated list in the environment, e.g. "http://localhost:3000,http://localhost:3001"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
