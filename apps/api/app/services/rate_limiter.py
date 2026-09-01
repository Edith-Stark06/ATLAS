"""Fixed-window rate limiting, backed by Redis so it holds across replicas
rather than resetting per-process.

Deliberately not `slowapi`/`fastapi-limiter`: the counting logic this needs
is a handful of lines, and this codebase already prefers owning its core
logic (trust, policy, simulation engines are all hand-written) over pulling
in a framework for something this small.
"""

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    #: Requests left in the current window, floored at 0.
    remaining: int
    #: Seconds until the window resets — used for the `Retry-After` header.
    retry_after: int


async def check_rate_limit(
    redis: Redis, key: str, *, limit: int, window_seconds: int
) -> RateLimitResult:
    """Increment `key`'s counter and report whether it's still within `limit`.

    A window starts on a key's first request and expires `window_seconds`
    later — not aligned to wall-clock boundaries, which is fine for abuse
    protection and simpler than a sliding log. `INCR` is atomic; the `EXPIRE`
    that follows it on the first hit is not part of the same atomic op, so a
    process crash in that exact gap could leave a key without a TTL. Rare
    enough, and low-stakes enough (a stuck counter just means one client's
    budget doesn't reset until touched again), not to warrant a Lua script
    for this use case.
    """
    bucket = f"ratelimit:{key}"
    count = await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, window_seconds)

    ttl = await redis.ttl(bucket)
    retry_after = ttl if ttl > 0 else window_seconds

    return RateLimitResult(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after=retry_after,
    )
