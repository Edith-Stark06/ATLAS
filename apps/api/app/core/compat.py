"""Platform compatibility shims."""

import asyncio
import sys
import warnings


def configure_event_loop() -> None:
    """Force a selector-based event loop on Windows.

    psycopg3's async driver cannot run on Windows' default ProactorEventLoop.
    Only affects local Windows development — on Linux (Docker, CI, production)
    this is a no-op.

    The policy API is deprecated in Python 3.14 but remains the only mechanism
    uvicorn honours; `asyncio.run(loop_factory=...)` isn't reachable through
    uvicorn's reload supervisor. Revisit once uvicorn exposes `loop_factory`.
    """
    if sys.platform != "win32":
        return

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
