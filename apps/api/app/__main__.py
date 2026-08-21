"""Dev entrypoint: `python -m app`.

Exists to force a selector-based event loop on Windows. psycopg3's async
driver cannot run on a ProactorEventLoop, and uvicorn picks the loop like
this (uvicorn/loops/asyncio.py):

    if sys.platform == "win32" and not use_subprocess:
        return asyncio.ProactorEventLoop
    return asyncio.SelectorEventLoop

so a single-process server gets Proactor and every database call fails,
while `--reload` happens to get Selector only because it runs in a
subprocess. Relying on that is a trap: turning reload off silently breaks
the database.

Passing the factory explicitly makes the choice independent of reload. This
supersedes the older event-loop *policy* shim — uvicorn >= 0.36 selects a
loop factory and ignores the policy, so setting the policy was a no-op here.
"""

import asyncio
import sys
from collections.abc import Callable

import uvicorn

from app.core.config import get_settings


def loop_factory() -> Callable[[], asyncio.AbstractEventLoop]:
    """SelectorEventLoop on Windows, the platform default elsewhere."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop
    return asyncio.new_event_loop


def main() -> None:
    settings = get_settings()
    # reload_dirs only when reloading — passing it otherwise makes uvicorn warn
    # that "configuration will not reload", which reads like a real failure.
    reload_options = {"reload_dirs": ["app"]} if settings.api_reload else {}
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        loop=loop_factory(),
        reload=settings.api_reload,
        **reload_options,
    )


if __name__ == "__main__":
    main()
