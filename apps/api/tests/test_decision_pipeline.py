"""Decision pipeline and governance ledger, against a seeded database.

These cover what only the committing path can show: that a decision and its
audit record are written together, that the ledger pins the rule versions and
model actually used, and that the chain still verifies afterwards.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import uuid

import pytest

TRAVEL_AGENT = "agt-travel-01"
FRAUD_AGENT = "agt-fraud-04"


def execute(client, **overrides):
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


# --- the pipeline commits ----------------------------------------------------


def test_executing_creates_a_retrievable_decision(client):
    result = execute(client)
    stored = client.get(f"/api/v1/decisions/{result['decisionId']}")

    assert stored.status_code == 200
    assert stored.json()["outcome"] == result["outcome"]


def test_a_low_risk_action_is_cleared_to_run(client):
    result = execute(client, amountUsd=40, riskScore=5)

    assert result["outcome"] == "approved"
    assert result["executed"] is True
    assert result["expectedExposureUsd"] == pytest.approx(40)


def test_a_blocked_action_is_not_cleared_to_run(client):
    """`executed` is what a caller branches on before moving money, so it
    must never be true for a blocked outcome."""
    result = execute(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)

    assert result["outcome"] == "blocked"
    assert result["executed"] is False
    assert result["expectedExposureUsd"] == 0
    assert result["withheldUsd"] == pytest.approx(4820)


def test_every_policy_is_recorded_not_just_the_failures(client):
    """A clean decision must be distinguishable from one where nothing was
    checked."""
    result = execute(client)
    stored = client.get(f"/api/v1/decisions/{result['decisionId']}").json()

    policies = client.get("/api/v1/policy/policies").json()
    enabled = [p for p in policies if p["enabled"]]
    assert len(stored["policyChecks"]) == len(enabled)


def test_the_decision_carries_the_simulation_that_decided_it(client):
    result = execute(client)
    runs = client.get("/api/v1/simulations").json()

    attached = [r for r in runs if r["decisionId"] == result["decisionId"]]
    assert len(attached) == 1
    assert attached[0]["recommendation"] == result["outcome"]


def test_executing_updates_the_agent_activity(client):
    before = client.get(f"/api/v1/agents/{FRAUD_AGENT}").json()
    execute(client, action="Refresh merchant risk profile")
    after = client.get(f"/api/v1/agents/{FRAUD_AGENT}").json()

    assert after["decisionsToday"] == before["decisionsToday"] + 1
    assert after["lastDecision"] == "Refresh merchant risk profile"


def test_a_caller_supplied_reference_is_honoured(client):
    """Enterprise systems have their own transaction ids; the ledger has to
    be searchable by the reference the business actually uses."""
    reference = f"TRX-CALLER-{uuid.uuid4().hex[:8].upper()}"
    result = execute(client, decisionId=reference)

    assert result["decisionId"] == reference


def test_a_replayed_reference_is_refused(client):
    """A retry after a timeout must not produce a second decision for one
    event, nor a raw database error."""
    reference = f"TRX-RETRY-{uuid.uuid4().hex[:8].upper()}"
    execute(client, decisionId=reference)

    response = client.post(
        "/api/v1/decisions/execute",
        json={"agentId": FRAUD_AGENT, "action": "x", "riskScore": 10, "decisionId": reference},
    )
    assert response.status_code == 409

    entries = client.get("/api/v1/ledger", params={"subjectId": reference}).json()
    assert len(entries) == 1, "the refused retry must not have written an audit record"


def test_an_unknown_agent_is_rejected(client):
    response = client.post(
        "/api/v1/decisions/execute",
        json={"agentId": "agt-nope", "action": "x", "riskScore": 10},
    )
    assert response.status_code == 404


# --- the ledger records it ---------------------------------------------------


def test_a_decision_writes_exactly_one_ledger_entry(client):
    result = execute(client)
    entries = client.get("/api/v1/ledger", params={"subjectId": result["decisionId"]}).json()

    assert len(entries) == 1
    assert entries[0]["seq"] == result["ledgerSeq"]
    assert entries[0]["entryHash"] == result["ledgerHash"]


def test_the_ledger_pins_the_policy_versions_in_force(client):
    """A policy renamed or re-authored later must not change what this
    decision is judged against."""
    result = execute(client)
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()

    evaluated = entry["payload"]["policy"]["evaluated"]
    assert evaluated
    assert all(rule["version"] for rule in evaluated)


def test_the_ledger_pins_the_model_that_scored_it(client):
    result = execute(client)
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()
    stats = client.get("/api/v1/ledger/stats").json()

    assert entry["payload"]["model"]["fingerprint"] == stats["modelFingerprint"]


def test_the_ledger_records_the_outcome_and_the_money(client):
    result = execute(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()

    assert entry["payload"]["decision"]["outcome"] == "blocked"
    assert entry["payload"]["exposure"]["expectedUsd"] == "0.00"
    assert entry["payload"]["exposure"]["withheldUsd"] == "4820.00"


def test_the_ledger_pins_the_inputs_actually_used(client):
    """Defaults are resolved before evaluation. Recording an omitted hour as
    null would pin an input the engine never used, and a decision an auditor
    cannot reproduce is not evidence of anything."""
    result = execute(client)  # no hourUtc supplied
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()

    assert entry["payload"]["inputs"]["hourUtc"] is not None
    assert 0 <= entry["payload"]["inputs"]["hourUtc"] <= 23


def test_a_supplied_hour_is_pinned_as_given(client):
    result = execute(client, hourUtc=3)
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()

    assert entry["payload"]["inputs"]["hourUtc"] == 3


def test_amounts_are_recorded_as_strings(client):
    """Hashing a float would make the audit record depend on repr precision."""
    result = execute(client, amountUsd=12450.5)
    entry = client.get(f"/api/v1/ledger/{result['ledgerSeq']}").json()

    assert entry["payload"]["decision"]["amountUsd"] == "12450.50"


# --- the chain holds ---------------------------------------------------------


def test_the_chain_verifies_after_writing_decisions(client):
    execute(client)
    execute(client, agentId=TRAVEL_AGENT, amountUsd=9000, riskScore=88)

    verification = client.get("/api/v1/ledger/verify").json()
    assert verification["valid"] is True, verification["breaks"]
    assert verification["breaks"] == []


def test_each_entry_links_to_the_one_before_it(client):
    execute(client)
    execute(client)

    entries = client.get("/api/v1/ledger", params={"limit": 3}).json()
    newest, middle = entries[0], entries[1]
    assert newest["prevHash"] == middle["entryHash"]


def test_sequence_numbers_are_monotonic(client):
    first = execute(client)
    second = execute(client)

    assert second["ledgerSeq"] > first["ledgerSeq"]


def test_stats_report_the_head_of_the_chain(client):
    result = execute(client)
    stats = client.get("/api/v1/ledger/stats").json()

    assert stats["headSeq"] == result["ledgerSeq"]
    assert stats["headHash"] == result["ledgerHash"]
    assert stats["entries"] >= 1


def test_verification_recomputes_rather_than_trusting_a_flag(client):
    """The head hash reported by /verify must match the stored head — if
    verification returned a cached boolean this would drift."""
    execute(client)

    stats = client.get("/api/v1/ledger/stats").json()
    verification = client.get("/api/v1/ledger/verify").json()

    assert verification["headHash"] == stats["headHash"]
    assert verification["entriesChecked"] == stats["entries"]


def test_an_unknown_ledger_entry_is_a_404(client):
    assert client.get("/api/v1/ledger/999999").status_code == 404


# --- tamper detection against real stored rows -------------------------------


async def test_editing_a_stored_entry_breaks_verification(client):
    """The headline claim, exercised against rows that came out of Postgres
    rather than a fixture.

    The edit is made inside a transaction that is always rolled back — the
    point is to prove detection works, not to leave a falsified audit record
    behind. Verification runs on the in-session objects, so the tampered
    state is visible to the check without ever being committed.
    """
    from app.core.database import AsyncSessionLocal
    from app.services import ledger, ledger_service

    async with AsyncSessionLocal() as session:
        try:
            entries = await ledger_service.load_chain(session)
            if len(entries) < 2:
                pytest.skip("needs at least two ledger entries")

            assert ledger.verify_chain(entries).valid is True

            target = entries[len(entries) // 2]
            original = target.payload.get("decision", {}).get("outcome")

            # Flip a recorded verdict — the exact edit an insider would make.
            # Must differ from what is already stored, or the "tamper" is a
            # no-op and the test would pass without proving anything.
            forged = "blocked" if original == "approved" else "approved"
            tampered = dict(target.payload)
            tampered["decision"] = {**tampered.get("decision", {}), "outcome": forged}
            target.payload = tampered
            assert forged != original

            result = ledger.verify_chain(entries)

            assert result.valid is False
            broken = [b for b in result.breaks if b.seq == target.seq]
            assert broken, f"editing seq {target.seq} went undetected"
            assert "stored hash" in broken[0].reason
        finally:
            await session.rollback()

    # The committed ledger is untouched.
    assert client.get("/api/v1/ledger/verify").json()["valid"] is True
