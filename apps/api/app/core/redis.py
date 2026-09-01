"""The Redis client — provisioned in both compose files since Phase 0, never
once imported by application code until the rate limiter needed a shared
counter store.

Not a plain `@lru_cache` singleton: redis-py's asyncio client binds its
connection pool to whatever event loop is running when it's created, and
this codebase's own test suite legitimately spins up more than one
independent `TestClient(app)` — each running its own ASGI lifespan on its
own loop (see tests/test_health.py). A bare cache-forever singleton would
hand a second lifespan a client wired to the first lifespan's already-closed
loop, failing with "Future attached to a different loop" the moment it's
used or closed. Rebinding when the running loop changes costs nothing in a
real deployment, which only ever has one loop for the process's whole life.
"""

import asyncio

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def get_redis_client() -> Redis:
    global _client, _client_loop

    current_loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not current_loop:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=True)
        _client_loop = current_loop

    return _client


async def close_redis_client() -> None:
    """Called from the app lifespan, alongside `engine.dispose()`."""
    global _client, _client_loop

    if _client is None:
        return
    try:
        await _client.aclose()
    except Exception:  # noqa: BLE001 - best-effort; the loop may already be tearing down
        pass
    finally:
        _client = None
        _client_loop = None
