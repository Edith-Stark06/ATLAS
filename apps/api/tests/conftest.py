"""Pytest bootstrap and shared fixtures.

`python -m app` installs the Windows selector event loop before uvicorn
starts, but pytest has no such entrypoint — without this, psycopg3 cannot
connect and every database-backed test would skip.
"""

from app.core.compat import configure_event_loop

configure_event_loop()

from collections.abc import Iterator  # noqa: E402 - must come after the loop shim

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def _new_client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        if c.get("/api/v1/health").json()["status"] != "healthy":
            pytest.skip("database unavailable — start it with `npm run db:up`")
        yield c


@pytest.fixture(scope="session")
def api() -> Iterator[TestClient]:
    """Client that never carries credentials.

    Its own instance rather than a view onto `client`: setting a header on a
    shared client would leave this one authenticated for the rest of the
    session, and every "rejects anonymous callers" assertion would pass for
    the wrong reason — or not, depending on test ordering.
    """
    yield from _new_client()


@pytest.fixture(scope="session")
def client(api: TestClient) -> Iterator[TestClient]:
    """Client authenticated as the bootstrap admin.

    Admin rather than a narrower role because most tests exercise behaviour,
    not authorisation — the permission boundaries are covered explicitly in
    test_auth.py, where a weaker credential is the point.
    """
    settings = get_settings()
    response = api.post(
        "/api/v1/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    if response.status_code != 200:
        pytest.skip(
            "bootstrap admin unavailable — run `python -m app.seed` to create it "
            f"(login returned {response.status_code})"
        )

    for authenticated in _new_client():
        authenticated.headers["Authorization"] = f"Bearer {response.json()['accessToken']}"
        yield authenticated
