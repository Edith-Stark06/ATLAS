"""Pytest bootstrap.

`python -m app` installs the Windows selector event loop before uvicorn starts,
but pytest has no such entrypoint — without this, psycopg3 cannot connect and
every database-backed test would skip.
"""

from app.core.compat import configure_event_loop

configure_event_loop()
