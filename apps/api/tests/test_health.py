from fastapi.testclient import TestClient

from app.main import app


def test_root_returns_service_metadata():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "atlas-api"
    assert body["health"] == "/api/v1/health"


def test_health_reports_dependency_status():
    """Health must answer even when Postgres is unreachable, reporting
    'degraded' rather than raising — the frontend relies on this."""
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "atlas-api"
    assert body["status"] in {"healthy", "degraded"}

    postgres = next(d for d in body["dependencies"] if d["name"] == "postgres")
    assert postgres["status"] in {"up", "down"}
    # A healthy overall status implies every dependency is up.
    if body["status"] == "healthy":
        assert postgres["status"] == "up"
