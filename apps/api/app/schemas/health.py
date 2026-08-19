from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    name: str
    status: Literal["up", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    version: str
    environment: str
    dependencies: list[DependencyHealth]
