from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.schemas.health import DependencyHealth, HealthResponse

router = APIRouter(tags=["health"])


async def _check_database() -> DependencyHealth:
    """Probe the database with a trivial query.

    Never raises — a down dependency is reported, not thrown, so the health
    endpoint stays reachable while Postgres is starting up.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return DependencyHealth(name="postgres", status="up")
    except Exception as exc:  # noqa: BLE001 - surface any driver/connection failure
        return DependencyHealth(name="postgres", status="down", detail=str(exc).split("\n")[0])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    dependencies = [await _check_database()]
    all_up = all(dep.status == "up" for dep in dependencies)

    return HealthResponse(
        status="healthy" if all_up else "degraded",
        service="atlas-api",
        version=__version__,
        environment=settings.environment,
        dependencies=dependencies,
    )
