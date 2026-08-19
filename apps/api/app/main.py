from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="ATLAS API",
    description=(
        "Adaptive Trust & Lifecycle Assurance System — governance layer "
        "for autonomous financial agents."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": "atlas-api",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
