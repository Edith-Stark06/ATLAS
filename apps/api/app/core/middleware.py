"""Request-scoped correlation and rate limiting.

Two middlewares, kept in one module because they share the same shape
(Starlette `BaseHTTPMiddleware`) and are always registered together in
`app/main.py` — splitting them into separate files would just mean jumping
between two small files to see the whole request pipeline.
"""

import logging
import time
import uuid
from contextvars import ContextVar

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.rate_limiter import check_rate_limit

#: Set for the lifetime of one request; read by `JSONFormatter`
#: (`app/core/logging.py`) so every log line emitted while handling a
#: request — not just the access-log line below — carries the same ID.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_access_log = logging.getLogger("atlas.access")
_rate_limit_log = logging.getLogger("atlas.ratelimit")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates a request ID and logs one structured line per
    request. Registered first (outermost) so the ID covers everything else,
    including the rate limiter below.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            _access_log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            return response
        finally:
            # In `finally` rather than after the block: a request that
            # raises past `call_next` (no exception handler matched it —
            # genuinely unexpected) must not leak this request's ID into
            # whatever the ASGI server logs next on the same task.
            request_id_var.reset(token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiting, keyed by client IP.

    Deployed behind a reverse proxy, `request.client.host` is the proxy's own
    address unless the proxy is configured to be trusted and its
    `X-Forwarded-For` honoured — out of scope here (a proxy-specific
    trust/parsing decision, not a bug in this middleware), same "documented
    boundary" as the ledger's multi-writer-safety note elsewhere in this
    codebase.
    """

    _EXEMPT_PATHS = frozenset({"/", "/docs", "/openapi.json", "/api/v1/health"})
    _LOGIN_PATH = "/api/v1/auth/login"
    _WINDOW_SECONDS = 60

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        is_login = request.method == "POST" and request.url.path == self._LOGIN_PATH
        scope = "login" if is_login else "general"
        limit = settings.rate_limit_login_per_minute if is_login else settings.rate_limit_per_minute

        try:
            result = await check_rate_limit(
                get_redis_client(),
                f"{scope}:{client_ip}",
                limit=limit,
                window_seconds=self._WINDOW_SECONDS,
            )
        except RedisError as exc:
            # The limiter must not become a new single point of failure for
            # the whole API — a Redis hiccup should degrade to "unthrottled",
            # not "down".
            _rate_limit_log.warning(
                "rate limiter unavailable, failing open", extra={"error": str(exc)}
            )
            return await call_next(request)

        if not result.allowed:
            return JSONResponse(
                {"error": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(result.retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response
