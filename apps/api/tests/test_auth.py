"""Authentication and authorisation.

The permission boundaries are the point here, so these tests deliberately use
weaker credentials than the shared `client` fixture — which is an admin, and
would sail through every check without proving anything.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings

FRAUD_AGENT = "agt-fraud-04"
TRAVEL_AGENT = "agt-travel-01"


def mint_key(client: TestClient, **overrides) -> str:
    """Create an API key and return its one-time secret."""
    payload = {"name": f"test-{uuid.uuid4().hex[:8]}", "role": "viewer"}
    payload.update(overrides)
    response = client.post("/api/v1/auth/api-keys", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["token"]


def as_key(api: TestClient, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- password hashing --------------------------------------------------------


def test_a_password_is_never_stored_in_recoverable_form():
    stored = security.hash_password("correct horse battery staple")

    assert "correct horse battery staple" not in stored
    assert stored.startswith("$argon2")


def test_the_same_password_hashes_differently_each_time():
    """Per-hash salting. Identical hashes would reveal that two accounts share
    a password."""
    assert security.hash_password("same") != security.hash_password("same")


def test_password_verification_accepts_the_right_one():
    assert security.verify_password("hunter2", security.hash_password("hunter2"))


def test_password_verification_rejects_the_wrong_one():
    assert not security.verify_password("hunter3", security.hash_password("hunter2"))


def test_a_corrupt_hash_reads_as_a_failed_login_not_a_crash():
    """A malformed row must not become a 500 that tells an attacker the
    account exists and is in an unusual state."""
    assert not security.verify_password("anything", "not-a-real-hash")


# --- tokens ------------------------------------------------------------------


def test_a_token_round_trips():
    token = security.create_access_token("someone@atlas.local", role="viewer")
    claims = security.decode_access_token(token)

    assert claims["sub"] == "someone@atlas.local"
    assert claims["role"] == "viewer"


def test_a_token_signed_with_another_key_is_rejected():
    """The whole basis of the scheme — without this, anyone could mint an
    admin token."""
    import jwt

    forged = jwt.encode(
        {"sub": "attacker@evil.test", "role": "admin", "exp": 9999999999, "iss": "atlas"},
        "some-other-secret",
        algorithm="HS256",
    )
    with pytest.raises(security.InvalidToken):
        security.decode_access_token(forged)


def test_an_unsigned_token_is_rejected():
    """`alg: none` is the classic JWT bypass; algorithms are pinned so it
    cannot be negotiated by the token itself."""
    import jwt

    unsigned = jwt.encode(
        {"sub": "attacker@evil.test", "role": "admin", "exp": 9999999999, "iss": "atlas"},
        key="",
        algorithm="none",
    )
    with pytest.raises(security.InvalidToken):
        security.decode_access_token(unsigned)


def test_an_expired_token_is_rejected():
    from datetime import timedelta

    expired = security.create_access_token(
        "someone@atlas.local", role="admin", expires_in=timedelta(seconds=-1)
    )
    with pytest.raises(security.InvalidToken):
        security.decode_access_token(expired)


# --- API key material --------------------------------------------------------


def test_generated_keys_are_unique():
    assert security.generate_api_key().token != security.generate_api_key().token


def test_only_the_hash_of_a_key_is_stored():
    generated = security.generate_api_key()

    assert generated.token not in generated.token_hash
    assert len(generated.token_hash) == 64
    # The prefix is short enough not to be a usable secret on its own.
    assert generated.token.startswith(generated.prefix)
    assert len(generated.prefix) < len(generated.token) / 2


# --- login -------------------------------------------------------------------


def test_login_returns_a_usable_token(api: TestClient):
    settings = get_settings()
    response = api.post(
        "/api/v1/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"

    me = api.get("/api/v1/auth/me", headers=as_key(api, body["accessToken"]))
    assert me.status_code == 200
    assert me.json()["kind"] == "user"


def test_a_wrong_password_is_rejected(api: TestClient):
    settings = get_settings()
    response = api.post(
        "/api/v1/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": "definitely-wrong"},
    )
    assert response.status_code == 401


def test_an_unknown_account_gives_the_same_answer_as_a_wrong_password(api: TestClient):
    """Different messages would turn the login form into an account
    enumeration oracle."""
    settings = get_settings()
    unknown = api.post(
        "/api/v1/auth/login",
        json={"email": "nobody@atlas.local", "password": "whatever"},
    )
    wrong = api.post(
        "/api/v1/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": "definitely-wrong"},
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


# --- what is reachable without credentials -----------------------------------


def test_the_anonymous_fixture_really_is_anonymous(api: TestClient, client: TestClient):
    """Guards the tests below rather than the app.

    An earlier version of the fixtures set the auth header on the shared
    client, so `api` silently became authenticated once `client` had been
    used — and every "rejects anonymous callers" assertion started passing
    for the wrong reason, depending on test ordering.
    """
    assert "Authorization" not in api.headers
    assert "Authorization" in client.headers


def test_health_stays_open(api: TestClient):
    """A load balancer polls this before it has any credential to present."""
    assert api.get("/api/v1/health").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/agents",
        "/api/v1/decisions",
        "/api/v1/dashboard",
        "/api/v1/ledger",
        "/api/v1/ledger/verify",
        "/api/v1/policy/policies",
        "/api/v1/trust/overview",
        "/api/v1/simulations",
    ],
)
def test_governance_data_is_not_public(api: TestClient, path: str):
    """Trust scores and decision rationales are not public information."""
    assert api.get(path).status_code == 401


def test_committing_a_decision_requires_credentials(api: TestClient):
    response = api.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "x", "riskScore": 10},
    )
    assert response.status_code == 401


def test_a_malformed_authorization_header_is_rejected(api: TestClient):
    for header in ["", "Bearer", "Basic abc123", "token abc123"]:
        response = api.get("/api/v1/agents", headers={"Authorization": header})
        assert response.status_code == 401, header


def test_a_401_says_how_to_authenticate(api: TestClient):
    response = api.get("/api/v1/agents")
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# --- role boundaries ---------------------------------------------------------


def test_a_viewer_can_read(client: TestClient, api: TestClient):
    token = mint_key(client, role="viewer")
    assert api.get("/api/v1/agents", headers=as_key(api, token)).status_code == 200


@pytest.mark.parametrize(
    "method,path,body",
    [
        (
            "post",
            "/api/v1/decisions/execute",
            {"agentId": FRAUD_AGENT, "action": "x", "riskScore": 5},
        ),
        ("post", "/api/v1/trust/recompute", None),
        ("post", "/api/v1/simulation/rebuild", None),
    ],
)
def test_a_viewer_cannot_write(client: TestClient, api: TestClient, method, path, body):
    token = mint_key(client, role="viewer")
    response = getattr(api, method)(path, json=body, headers=as_key(api, token))

    assert response.status_code == 403
    # The message should say what is missing, not just refuse.
    assert "role" in response.json()["detail"].lower()


def test_an_operator_can_commit_a_decision(client: TestClient, api: TestClient):
    token = mint_key(client, role="operator")
    response = api.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "Operator action", "riskScore": 10},
        headers=as_key(api, token),
    )
    assert response.status_code == 200


def test_an_operator_cannot_author_policy(client: TestClient, api: TestClient):
    """Deciding under the rules and rewriting the rules are different powers."""
    token = mint_key(client, role="operator")
    response = api.post(
        "/api/v1/policy/policies/pol-01/versions",
        json={
            "rule": {
                "conditions": [{"field": "risk_score", "operator": "gt", "value": 50}],
                "combinator": "all",
                "effect": "block",
                "applies_to": [],
            },
            "version": "v99.0.0",
        },
        headers=as_key(api, token),
    )
    assert response.status_code == 403


def test_an_operator_cannot_manage_credentials(client: TestClient, api: TestClient):
    token = mint_key(client, role="operator")
    headers = as_key(api, token)

    assert api.get("/api/v1/auth/users", headers=headers).status_code == 403
    assert api.get("/api/v1/auth/api-keys", headers=headers).status_code == 403
    assert (
        api.post("/api/v1/auth/api-keys", json={"name": "escalate"}, headers=headers).status_code
        == 403
    )


def test_an_operator_cannot_register_an_agent(client: TestClient, api: TestClient):
    """Registering an agent changes what the estate governs — same admin-only
    bar as creating a user, not something an operator credential can do."""
    token = mint_key(client, role="operator")
    response = api.post(
        "/api/v1/agents",
        json={
            "id": "agt-test-operator-should-not-create-this",
            "name": "Should Not Exist",
            "capability": "Test Capability",
            "owner": "test-suite",
            "model": "test-model-v1",
        },
        headers=as_key(api, token),
    )
    assert response.status_code == 403


# --- agent-bound keys --------------------------------------------------------


def test_an_agent_bound_key_can_act_for_its_own_agent(client: TestClient, api: TestClient):
    token = mint_key(client, role="operator", agentId=TRAVEL_AGENT)
    response = api.post(
        "/api/v1/decisions/execute",
        json={"agentId": TRAVEL_AGENT, "action": "Book flight", "amountUsd": 100, "riskScore": 10},
        headers=as_key(api, token),
    )
    assert response.status_code == 200


def test_an_agent_bound_key_cannot_act_for_another_agent(client: TestClient, api: TestClient):
    """Otherwise one compromised agent credential could commit decisions in
    every other agent's name."""
    token = mint_key(client, role="operator", agentId=TRAVEL_AGENT)
    response = api.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "Freeze card", "riskScore": 10},
        headers=as_key(api, token),
    )

    assert response.status_code == 403
    assert TRAVEL_AGENT in response.json()["detail"]


# --- key lifecycle -----------------------------------------------------------


def test_a_key_is_only_revealed_once(client: TestClient):
    created = client.post("/api/v1/auth/api-keys", json={"name": "once"}).json()
    listed = client.get("/api/v1/auth/api-keys").json()

    match = next(k for k in listed if k["id"] == created["id"])
    assert "token" not in match, "listing keys must never return the secret"
    assert match["prefix"] == created["prefix"]


def test_a_revoked_key_stops_working(client: TestClient, api: TestClient):
    created = client.post("/api/v1/auth/api-keys", json={"name": "to-revoke"}).json()
    headers = as_key(api, created["token"])

    assert api.get("/api/v1/agents", headers=headers).status_code == 200

    client.delete(f"/api/v1/auth/api-keys/{created['id']}")
    assert api.get("/api/v1/agents", headers=headers).status_code == 401


def test_a_revoked_key_is_kept_for_the_audit_trail(client: TestClient):
    """Its prefix appears as the actor behind past decisions; deleting the row
    would leave those records naming a credential nobody can identify."""
    created = client.post("/api/v1/auth/api-keys", json={"name": "keep-me"}).json()
    client.delete(f"/api/v1/auth/api-keys/{created['id']}")

    listed = client.get("/api/v1/auth/api-keys").json()
    match = next(k for k in listed if k["id"] == created["id"])
    assert match["active"] is False


def test_an_expired_key_is_rejected(client: TestClient, api: TestClient):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models import ApiKey

    created = client.post("/api/v1/auth/api-keys", json={"name": "expiring"}).json()

    async def backdate():
        async with AsyncSessionLocal() as session:
            key = (
                await session.execute(select(ApiKey).where(ApiKey.id == created["id"]))
            ).scalar_one()
            key.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

    import asyncio

    asyncio.run(backdate())

    assert api.get("/api/v1/agents", headers=as_key(api, created["token"])).status_code == 401


# --- user management ---------------------------------------------------------


def test_an_admin_can_create_a_user(client: TestClient, api: TestClient):
    email = f"user-{uuid.uuid4().hex[:8]}@atlas.local"
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": email,
            "name": "Test User",
            "password": "a-long-enough-password",
            "role": "viewer",
        },
    )
    assert response.status_code == 201

    login = api.post(
        "/api/v1/auth/login", json={"email": email, "password": "a-long-enough-password"}
    )
    assert login.status_code == 200
    assert login.json()["role"] == "viewer"


def test_duplicate_emails_are_refused(client: TestClient):
    email = f"dupe-{uuid.uuid4().hex[:8]}@atlas.local"
    body = {"email": email, "name": "First", "password": "a-long-enough-password"}

    assert client.post("/api/v1/auth/users", json=body).status_code == 201
    assert client.post("/api/v1/auth/users", json=body).status_code == 409


def test_a_short_password_is_refused(client: TestClient):
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": f"short-{uuid.uuid4().hex[:6]}@atlas.local",
            "name": "X",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_internal_domains_are_accepted(client: TestClient):
    """`.local` and friends are what an internal console actually runs on;
    strict RFC deliverability validation would reject the whole estate."""
    response = client.post(
        "/api/v1/auth/users",
        json={
            "email": f"ops-{uuid.uuid4().hex[:6]}@atlas.internal",
            "name": "Ops",
            "password": "a-long-enough-password",
        },
    )
    assert response.status_code == 201


# --- actor attribution -------------------------------------------------------


def test_the_ledger_records_which_credential_committed_a_decision(
    client: TestClient, api: TestClient
):
    """'The system approved it' is not an answer anyone can act on."""
    token = mint_key(client, role="operator", name="attribution-probe")
    committed = api.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "Attributed action", "riskScore": 12},
        headers=as_key(api, token),
    ).json()

    entry = client.get(f"/api/v1/ledger/{committed['ledgerSeq']}").json()
    actor = entry["payload"]["decision"]["actor"]

    assert actor.startswith("api_key:")
    assert actor != "system"


def test_a_user_and_a_key_are_distinguishable_as_actors(client: TestClient):
    committed = client.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "User action", "riskScore": 12},
    ).json()

    entry = client.get(f"/api/v1/ledger/{committed['ledgerSeq']}").json()
    assert entry["payload"]["decision"]["actor"].startswith("user:")


def test_attribution_is_covered_by_the_chain_hash(client: TestClient):
    """Rewriting who did something must be no easier than rewriting what
    they did."""
    committed = client.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "Hashed attribution", "riskScore": 12},
    ).json()

    from app.services.ledger import LedgerKind, compute_hash

    entry = client.get(f"/api/v1/ledger/{committed['ledgerSeq']}").json()
    payload = entry["payload"]

    from datetime import datetime

    recorded_at = datetime.fromisoformat(entry["recordedAt"].replace("Z", "+00:00"))
    tampered = {**payload, "decision": {**payload["decision"], "actor": "user:someone-else"}}

    assert (
        compute_hash(
            seq=entry["seq"],
            prev_hash=entry["prevHash"],
            kind=LedgerKind.DECISION_RECORDED,
            subject_id=entry["subjectId"],
            recorded_at=recorded_at,
            payload=tampered,
        )
        != entry["entryHash"]
    )
