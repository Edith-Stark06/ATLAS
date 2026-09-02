"""Live demonstration: register two real agents through the API (not the
seeder), give them credentials, have them commit real decisions, and check
where they land in a real benchmark ranking.

This is a one-off manual demo, not part of the automated test suite — see
docs/PROJECT_MEMORY.md's "Agent Registration" note for why: a committed
decision writes a permanent, hash-chained ledger entry that cannot be
deleted afterward without breaking tamper-evidence for everything decided
after it (deliberately — that's the mechanism working as designed). The
agents this script creates stay in the estate afterward, same as any
seeded agent.

Requires a running API (`python -m app`) and a seeded database. Run with:
    .venv/Scripts/python.exe demo_onboard_agent.py
"""

import random

import httpx

from app.core.config import get_settings

BASE = "http://localhost:8000/api/v1"
CAPABILITY = "Demo Import Test"

STRONG_AGENT = "agt-demo-import-strong"
WEAK_AGENT = "agt-demo-import-weak"


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _login(client: httpx.Client) -> dict[str, str]:
    settings = get_settings()
    response = client.post(
        "/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": settings.bootstrap_admin_password},
    )
    response.raise_for_status()
    token = response.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _register(client: httpx.Client, admin_headers: dict, agent_id: str, name: str) -> None:
    response = client.post(
        "/agents",
        json={
            "id": agent_id,
            "name": name,
            "capability": CAPABILITY,
            "owner": "demo-script",
            "model": "demo-agent-v1",
        },
        headers=admin_headers,
    )
    if response.status_code == 409:
        print(f"  {agent_id}: already registered (re-run of this script) — reusing it")
        return
    response.raise_for_status()
    agent = response.json()
    print(f"  Registered {agent_id}: lifecycle={agent['lifecycle']} trustScore={agent['trustScore']}")


def _mint_key(client: httpx.Client, admin_headers: dict, agent_id: str) -> dict[str, str]:
    response = client.post(
        "/auth/api-keys",
        json={"name": f"demo key for {agent_id}", "role": "operator", "agentId": agent_id},
        headers=admin_headers,
    )
    response.raise_for_status()
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _commit_decisions(
    client: httpx.Client, headers: dict, agent_id: str, *, n: int, risk_range: tuple[int, int], seed: int
) -> None:
    rng = random.Random(seed)
    outcomes: dict[str, int] = {}
    for i in range(n):
        risk = rng.randint(*risk_range)
        amount = round(rng.uniform(50, 25_000), 2)
        response = client.post(
            "/decisions/execute",
            json={
                "agentId": agent_id,
                "action": f"Demo transaction #{i + 1}",
                "amountUsd": amount,
                "riskScore": risk,
            },
            headers=headers,
        )
        response.raise_for_status()
        outcome = response.json()["outcome"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    print(f"  {agent_id}: committed {n} real decisions -> {outcomes}")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        _print_header("1. Authenticate as admin")
        admin_headers = _login(client)
        print("  Logged in.")

        _print_header("2. Register two real agents via POST /agents")
        _register(client, admin_headers, STRONG_AGENT, "Demo Strong Performer")
        _register(client, admin_headers, WEAK_AGENT, "Demo Weak Performer")

        _print_header("3. Mint each agent its own scoped credential")
        strong_headers = _mint_key(client, admin_headers, STRONG_AGENT)
        weak_headers = _mint_key(client, admin_headers, WEAK_AGENT)
        print("  Both keys minted.")

        _print_header("4. Each agent commits real decisions as itself")
        # Strong: low risk, enough volume to clear the thin-evidence bar (25).
        _commit_decisions(client, strong_headers, STRONG_AGENT, n=30, risk_range=(5, 35), seed=1)
        # Weak: high risk, deliberately under the thin-evidence bar.
        _commit_decisions(client, weak_headers, WEAK_AGENT, n=15, risk_range=(60, 98), seed=2)

        _print_header("5. Check real trust scores")
        for agent_id in (STRONG_AGENT, WEAK_AGENT):
            trust = client.get(f"/trust/agents/{agent_id}", headers=admin_headers).json()
            print(
                f"  {agent_id}: score={trust['score']} lifecycle={trust['lifecycle']} "
                f"source={trust['scoreSource']}"
            )

        _print_header("6. Check the real benchmark ranking")
        ranking = client.get(f"/benchmark/cohorts/{CAPABILITY}", headers=admin_headers).json()
        print(f"  Cohort: {ranking['capability']} | comparable={ranking['comparable']}")
        for rank, entry in enumerate(ranking["scored"], start=1):
            print(
                f"  #{rank} {entry['agentId']}: composite={entry['composite']} "
                f"decisions={entry['decisions']} thinEvidence={entry['thinEvidence']}"
            )
        print(f"  Leader: {ranking['leaderId']}")


if __name__ == "__main__":
    main()
