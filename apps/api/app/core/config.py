from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root — apps/api/app/core/config.py -> up 4 levels
REPO_ROOT = Path(__file__).resolve().parents[4]

#: The development JWT secret. Named and checked rather than merely commented
#: so shipping it is a startup failure, not a silent one — a signing key that
#: is public knowledge means anyone can mint an admin token.
DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"


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

    #: Auto-reload on source changes. Off by default despite being a dev
    #: convenience: uvicorn's reloader runs the app in a spawned child, and if
    #: the supervisor is killed abruptly that child is orphaned — it keeps
    #: holding the port and serving the code it started with, which looks
    #: exactly like "my changes aren't taking effect". Opt in with
    #: API_RELOAD=true when you want it.
    #:
    #: Safe to toggle either way: the Windows event loop is chosen explicitly in
    #: app/__main__.py, so it no longer depends on whether reload forks.
    api_reload: bool = False

    # Comma-separated list in the environment, e.g. "http://localhost:3000,http://localhost:3001"
    cors_origins: str = "http://localhost:3000"

    # --- auth ---------------------------------------------------------------

    #: HMAC signing key for access tokens. Must be overridden outside
    #: development; see the validator below.
    jwt_secret: str = DEV_JWT_SECRET

    #: Console sessions are short-lived because a leaked token cannot be
    #: revoked before it expires — the role is re-read per request, but the
    #: token itself stays valid until `exp`.
    access_token_minutes: int = 60

    #: Credentials for the bootstrap admin created by `python -m app.seed`.
    #: Only ever used to create the account when no users exist yet.
    bootstrap_admin_email: str = "admin@atlas.local"
    bootstrap_admin_password: str = "atlas-dev-admin"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        """Fail loudly at startup rather than serving with known-public keys.

        A misconfigured deployment that boots and appears healthy is far worse
        than one that refuses to start: the first is discovered by an attacker,
        the second by whoever runs the deploy.
        """
        if self.is_development:
            return self

        problems = []
        if self.jwt_secret == DEV_JWT_SECRET:
            problems.append("JWT_SECRET is still the development default")
        if len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be at least 32 characters")
        if self.bootstrap_admin_password == "atlas-dev-admin":
            problems.append("BOOTSTRAP_ADMIN_PASSWORD is still the development default")

        if problems:
            raise ValueError(
                f"Refusing to start in environment '{self.environment}': " + "; ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
