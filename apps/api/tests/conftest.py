"""Pytest bootstrap and shared fixtures.

`python -m app` installs the Windows selector event loop before uvicorn
starts, but pytest has no such entrypoint — without this, psycopg3 cannot
connect and every database-backed test would skip.
"""

from app.core.compat import configure_event_loop

configure_event_loop()

import pytest  # noqa: E402 - must come after the loop shim
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def _login(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
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
    return response.json()["accessToken"]


@pytest.fixture(scope="session")
def api() -> TestClient:
    """Unauthenticated client.

    Use this to assert that a route *rejects* anonymous callers; almost every
    other test wants `client`.
    """
    with TestClient(app) as c:
        if c.get("/api/v1/health").json()["status"] != "healthy":
            pytest.skip("database unavailable — start it with `npm run db:up`")
        yield c


@pytest.fixture(scope="session")
def client(api: TestClient) -> TestClient:
    """Client authenticated as the bootstrap admin.

    Admin rather than a narrower role because these tests exercise behaviour,
    not authorisation — the permission boundaries themselves are covered
    explicitly in test_auth.py, where a weaker credential is the point.
    """
    api.headers["Authorization"] = f"Bearer {_login(api)}"
    yield api
    api.headers.pop("Authorization", None)
