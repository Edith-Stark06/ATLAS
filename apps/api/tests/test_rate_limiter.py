"""Tests the rate limiter's counting logic directly against a real Redis
connection — not through the app, which runs with rate limiting disabled in
this suite (see conftest.py) so 479 tests from one TestClient "IP" aren't
mistaken for abuse.
"""

import uuid

import pytest
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.rate_limiter import check_rate_limit


@pytest.fixture
async def redis():
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis unavailable — start it with `npm run db:up`")
    yield client
    await client.aclose()


def _key() -> str:
    # A fresh key per test so runs never see another test's leftover count.
    return f"test:{uuid.uuid4()}"


async def test_requests_within_the_limit_are_allowed(redis):
    key = _key()
    for _ in range(3):
        result = await check_rate_limit(redis, key, limit=3, window_seconds=60)
        assert result.allowed is True


async def test_the_request_that_exceeds_the_limit_is_refused(redis):
    key = _key()
    for _ in range(3):
        await check_rate_limit(redis, key, limit=3, window_seconds=60)

    result = await check_rate_limit(redis, key, limit=3, window_seconds=60)

    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after > 0


async def test_remaining_counts_down_toward_zero(redis):
    key = _key()
    first = await check_rate_limit(redis, key, limit=5, window_seconds=60)
    second = await check_rate_limit(redis, key, limit=5, window_seconds=60)

    assert first.remaining == 4
    assert second.remaining == 3


async def test_different_keys_do_not_share_a_budget(redis):
    a, b = _key(), _key()
    for _ in range(3):
        await check_rate_limit(redis, a, limit=3, window_seconds=60)

    # `a` is now exhausted; `b` has never been touched and must be unaffected.
    result = await check_rate_limit(redis, b, limit=3, window_seconds=60)

    assert result.allowed is True
    assert result.remaining == 2
