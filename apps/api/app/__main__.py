"""Dev entrypoint: `python -m app`.

Exists mainly so the Windows event-loop shim in `app.core.compat` runs *before*
uvicorn creates its event loop. Importing it from inside the app package would
be too late — uvicorn loads the app only after the loop already exists.
"""

from app.core.compat import configure_event_loop

configure_event_loop()

import uvicorn  # noqa: E402 - must come after the loop shim

from app.core.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        reload_dirs=["app"],
    )


if __name__ == "__main__":
    main()
