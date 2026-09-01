from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.redis import close_redis_client

# Before anything else touches logging — uvicorn attaches its own handlers
# on startup, and configuring this after that would mean fighting whatever
# it already set up rather than replacing it cleanly.
configure_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await close_redis_client()


app = FastAPI(
    title="ATLAS API",
    description=(
        "Adaptive Trust & Lifecycle Assurance System — governance layer "
        "for autonomous financial agents."
    ),
    version=__version__,
    lifespan=lifespan,
)

# Order matters, and it's the opposite of reading order: Starlette's
# `add_middleware` prepends, so the *last* call here ends up *outermost* —
# first to see the request, last to see the response. Added innermost-first:
#   1. RateLimitMiddleware — innermost of the three, but still outside the
#      router, so a 429 never reaches route/auth logic at all.
#   2. CORSMiddleware — wraps the limiter so a 429 still carries CORS
#      headers (otherwise the browser reports a CORS failure instead of
#      surfacing the real 429 to the frontend).
#   3. RequestContextMiddleware — outermost, so its request ID and access
#      log cover every response this app produces, rate-limited and
#      preflight requests included, with `duration_ms` measuring the full
#      request as the client experienced it.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": "atlas-api",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
