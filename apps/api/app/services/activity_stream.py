"""Publishes and streams the live governance activity feed.

`ActivityItem` ("An entry in the live governance activity feed",
app/models/activity.py) existed before this module did, with a read
endpoint (GET /activity) and a spot on the console dashboard — but nothing
ever wrote to it at runtime; the only rows that ever existed came from
app/seed.py's demo data. `decision_service.execute` now writes a real one
per committed decision (same transaction as the decision itself) and calls
`publish()` afterward so a browser watching the console sees it appear
without a refresh.

Redis Pub/Sub, not an in-process event bus: multiple API replicas are
already anticipated elsewhere in this codebase (rate_limiter.py's own
docstring; docker-compose.prod.yml's migrate-service comment about races
between replicas) — an in-process bus would miss every event committed on
a different replica than the one a given browser's stream is attached to.
"""

import json
import logging
from collections.abc import AsyncIterator

from redis.exceptions import RedisError

from app.core.redis import get_redis_client
from app.models import ActivityItem

ACTIVITY_CHANNEL = "atlas:activity"

#: How long a stream waits for a message before sending a heartbeat comment
#: (a bare `: ...` SSE line, ignored by EventSource but keeps intermediary
#: proxies and load balancers from treating an idle connection as dead).
HEARTBEAT_SECONDS = 15.0

_log = logging.getLogger("atlas.activity_stream")


def _payload(item: ActivityItem) -> str:
    return json.dumps(
        {
            "id": item.id,
            "message": item.message,
            "at": item.at.isoformat(),
            "tone": item.tone.value,
        }
    )


async def publish(item: ActivityItem) -> None:
    """Announce an activity item to every open stream.

    Call only after the item's own transaction has committed — never
    announce an event for data that didn't actually persist. Fails open on
    a Redis error (logs a warning, does not raise): the decision this
    accompanies already committed successfully by the time this runs, and
    a live-feed hiccup must not turn into a failed request for something
    that, as far as the ledger is concerned, already happened.
    """
    try:
        await get_redis_client().publish(ACTIVITY_CHANNEL, _payload(item))
    except RedisError as exc:
        _log.warning("failed to publish activity event, continuing", extra={"error": str(exc)})


async def events() -> AsyncIterator[str]:
    """SSE generator for GET /activity/stream.

    Each open stream gets its own dedicated Pub/Sub connection — redis-py's
    `.pubsub()` draws a separate connection from the pool rather than
    hijacking the shared client's connection, so this doesn't interfere
    with the rate limiter's own use of that same client for INCR/EXPIRE.
    """
    redis = get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.subscribe(ACTIVITY_CHANNEL)
    try:
        yield ": connected\n\n"
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS
            )
            if message is not None:
                yield f"data: {message['data']}\n\n"
            else:
                yield ": heartbeat\n\n"
    finally:
        await pubsub.unsubscribe(ACTIVITY_CHANNEL)
        await pubsub.aclose()
