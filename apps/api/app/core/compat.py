"""Platform compatibility shims."""

import asyncio
import sys
import warnings


def configure_event_loop() -> None:
    """Force a selector-based event loop on Windows.

    psycopg3's async driver cannot run on Windows' default ProactorEventLoop.
    Only affects local Windows development — on Linux (Docker, CI, production)
    this is a no-op.

    Call this from entrypoints that reach the database through `asyncio.run`
    (alembic, the seeder, pytest), which builds its loop from the policy.

    It does *not* cover the API server: uvicorn >= 0.36 selects a loop factory
    and never consults the policy, so `python -m app` sets the loop itself.
    See `app/__main__.py`.
    """
    if sys.platform != "win32":
        return

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
