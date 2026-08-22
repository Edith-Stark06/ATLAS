"""Governance analytics endpoint, against a seeded database.

The unit tests cover the arithmetic. These cover what only the wired-up
system can show: that the window is really applied, that the figures agree
with the records they claim to summarise, and that the aggregates hold up
when a fresh decision lands.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

from fastapi.testclient import TestClient

FRAUD_AGENT = "agt-fraud-04"
TRAVEL_AGENT = "agt-travel-01"


def analytics(client: TestClient, **params) -> dict:
    response = client.get("/api/v1/analytics", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def commit(client: TestClient, **overrides) -> dict:
    payload = {
        "agentId": FRAUD_AGENT,
        "action": "Approve vendor payment",
        "amountUsd": 250,
        "riskScore": 15,
    }
    payload.update(overrides)
    response = client.post("/api/v1/decisions/execute", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- access ------------------------------------------------------------------


def test_analytics_require_credentials(api: TestClient):
    """Estate-wide trust and violation rates are not public information."""
    assert api.get("/api/v1/analytics").status_code == 401


def test_a_viewer_can_read_analytics(client: TestClient, api: TestClient):
    created = client.post("/api/v1/auth/api-keys", json={"name": "analytics-ro", "role": "viewer"})
    token = created.json()["token"]

    response = api.get("/api/v1/analytics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


# --- window ------------------------------------------------------------------


def test_the_window_is_honoured(client: TestClient):
    result = analytics(client, days=7)

    assert result["windowDays"] == 7
    assert len(result["series"]) == 7


def test_quiet_days_are_present_in_the_series(client: TestClient):
    """A chart that skips silent days makes a lull look like traffic."""
    result = analytics(client, days=30)
    assert len(result["series"]) == 30
    assert [p["day"] for p in result["series"]] == sorted(p["day"] for p in result["series"])


def test_an_absurd_window_is_rejected_rather_than_scanning_everything(client: TestClient):
    assert client.get("/api/v1/analytics", params={"days": 100_000}).status_code == 422
    assert client.get("/api/v1/analytics", params={"days": 0}).status_code == 422


# --- the figures agree with the records --------------------------------------


def test_the_outcome_mix_matches_the_series(client: TestClient):
    """Two independent aggregations of the same decisions must agree."""
    result = analytics(client, days=365)

    from_series = sum(p["total"] for p in result["series"])
    from_mix = sum(b["count"] for b in result["outcomes"])

    assert from_series == from_mix


def test_every_outcome_appears_even_at_zero(client: TestClient):
    labels = {b["label"] for b in analytics(client)["outcomes"]}
    assert labels == {"approved", "escalated", "blocked"}


def test_trust_buckets_cover_the_whole_estate(client: TestClient):
    result = analytics(client)
    agents = client.get("/api/v1/agents").json()

    assert sum(b["count"] for b in result["trust"]) == len(agents)
    assert {b["label"] for b in result["trust"]} == {
        "restricted",
        "watch",
        "healthy",
        "trusted",
    }


def test_rates_carry_their_denominator(client: TestClient):
    """A percentage without its sample size makes 1-in-12 look like
    1-in-12,000."""
    result = analytics(client, days=365)

    assert "total" in result["review"]["rate"]
    for hotspot in result["hotspots"]:
        assert hotspot["matchRate"]["total"] == hotspot["evaluations"]


# --- a new decision moves the numbers ----------------------------------------


def test_committing_a_decision_shows_up_in_the_window(client: TestClient):
    before = analytics(client, days=1)
    commit(client)
    after = analytics(client, days=1)

    assert after["series"][-1]["total"] == before["series"][-1]["total"] + 1


def test_a_blocked_decision_lands_in_withheld_not_moved(client: TestClient):
    before = analytics(client, days=1)["exposure"]
    commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    after = analytics(client, days=1)["exposure"]

    assert after["withheldUsd"] > before["withheldUsd"]
    assert after["movedUsd"] == before["movedUsd"]


def test_an_approved_decision_lands_in_moved(client: TestClient):
    before = analytics(client, days=1)["exposure"]
    commit(client, amountUsd=40, riskScore=5)
    after = analytics(client, days=1)["exposure"]

    assert after["movedUsd"] > before["movedUsd"]


def test_an_action_without_an_amount_moves_no_exposure(client: TestClient):
    """A card freeze is governed but carries no money; counting its absent
    amount as zero would drag the totals."""
    before = analytics(client, days=1)["exposure"]
    commit(client, amountUsd=None, action="Freeze card", riskScore=10)
    after = analytics(client, days=1)["exposure"]

    assert after["movedUsd"] == before["movedUsd"]
    assert after["withheldUsd"] == before["withheldUsd"]
    assert after["decisionsWithAmount"] == before["decisionsWithAmount"]


# --- latency -----------------------------------------------------------------


def test_latency_reports_percentiles_not_just_a_mean(client: TestClient):
    """ATLAS is in the critical path of the action, so the tail is what
    matters."""
    commit(client)
    latency = analytics(client, days=1)["latency"]

    assert latency["samples"] > 0
    assert latency["p50"] <= latency["p95"] <= latency["p99"] <= latency["max"]


def test_latency_percentiles_are_real_measurements(client: TestClient):
    """Nearest-rank, so every figure is a request that actually happened —
    no interpolated p99 that nobody ever measured."""
    commit(client)
    latency = analytics(client, days=365)["latency"]

    assert latency["p99"] <= latency["max"]
    assert latency["p50"] >= 0


# --- policy hotspots ---------------------------------------------------------


def test_hotspots_are_ranked_most_restrictive_first(client: TestClient):
    commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    hotspots = analytics(client, days=365)["hotspots"]

    if len(hotspots) < 2:
        return
    rates = [h["matchRate"]["percent"] for h in hotspots]
    assert rates == sorted(rates, reverse=True)


def test_a_policy_that_never_restricts_is_flagged_once_it_has_been_tested(client: TestClient):
    """Mis-scoped or redundant — either way an author should look. But only
    claimed after enough evaluations to mean something."""
    for _ in range(3):
        commit(client)

    hotspots = analytics(client, days=365)["hotspots"]
    for hotspot in hotspots:
        if hotspot["neverFired"]:
            assert hotspot["restrictions"] == 0
            assert hotspot["evaluations"] >= 20, (
                "a rule should not be called dead before it has been tested"
            )


def test_hotspot_evaluations_count_passes_as_well_as_failures(client: TestClient):
    """Counting only violations would make a clean rule indistinguishable
    from an unevaluated one."""
    commit(client)
    hotspots = analytics(client, days=365)["hotspots"]

    assert hotspots, "seeded policies should have been evaluated"
    assert all(h["evaluations"] >= h["restrictions"] for h in hotspots)


# --- estate ------------------------------------------------------------------


def test_estate_totals_are_reported(client: TestClient):
    result = analytics(client)
    agents = client.get("/api/v1/agents").json()

    assert result["agents"] == len(agents)
    assert result["decisionsAllTime"] >= 0
    assert 0 <= result["agentsWithoutDecisions"] <= result["agents"]
