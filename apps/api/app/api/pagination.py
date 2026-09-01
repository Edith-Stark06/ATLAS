"""Shared helper for paginated list endpoints.

Total row count is exposed as an `X-Total-Count` response header rather than
changing any response body from a bare array to a `{items, total}` envelope
— the frontend consumes every one of these as a plain array today and never
sends `limit`/`offset` itself (see docs/PROJECT_MEMORY.md), so a body-shape
change would break it. A header is additive: nothing that exists has to
change for this to be useful to a future paginated UI.
"""

from fastapi import Response


def set_total_count(response: Response, total: int) -> None:
    response.headers["X-Total-Count"] = str(total)
