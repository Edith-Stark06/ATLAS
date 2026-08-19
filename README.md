# ATLAS

**Adaptive Trust & Lifecycle Assurance System** — a governance layer that decides whether autonomous financial agents can be trusted *before* they act.

Traditional governance asks *"is this agent authorized to perform this action?"* ATLAS asks *"should this agent be trusted to perform this action, right now, under these circumstances?"*

Every autonomous action passes through a governance pipeline before execution:

```
Agent Request → Trust Engine → Policy Brain → Simulation Engine
             → Governance Decision → Explain AI → Governance Ledger → Execution
```

---

## Stack

| Layer | Technology |
| --- | --- |
| Web | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4 |
| API | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic |
| Data | PostgreSQL 17, Redis 7 |
| Design | Tokens exported from Stitch (`stitch_export/`) |

## Layout

```
apps/
  web/            Next.js frontend
  api/            FastAPI backend
infra/
  docker-compose.yml   Postgres + Redis
stitch_export/    Source design screens (HTML + screenshots + design tokens)
docs/
```

---

## Setup

Requires **Node 20+**, **Python 3.12+**, and **Docker**.

```bash
cp .env.example .env
```

### 1. Data services

```bash
npm run db:up
```

Postgres listens on **5433** and Redis on **6380** — deliberately off the default ports so ATLAS never collides with other local projects.

### 2. API

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# .venv/bin/python -m pip install -e ".[dev]"         # macOS / Linux
```

Run it:

```bash
cd apps/api && .venv/Scripts/python.exe -m app
```

Use `python -m app` rather than invoking `uvicorn` directly — the entrypoint installs a Windows event-loop shim that psycopg3 requires (see `app/core/compat.py`).

Apply migrations and load the reference dataset:

```bash
cd apps/api && .venv/Scripts/python.exe -m alembic upgrade head
```

```bash
cd apps/api && .venv/Scripts/python.exe -m app.seed --reset
```

API on <http://localhost:8000>, interactive docs at `/docs`.

### 3. Web

```bash
npm install
npm run dev
```

Web on <http://localhost:3000>.

---

## Useful commands

| Command | Description |
| --- | --- |
| `npm run dev` | Start the Next.js dev server |
| `npm run build` | Production build of the web app |
| `npm run db:up` / `db:down` | Start / stop Postgres + Redis |
| `npm run db:logs` | Tail data service logs |

---

## Console routes

| Route | Screen | Source |
| --- | --- | --- |
| `/` | Control Center dashboard | `atlas-control-center` |
| `/agents` | AI Agent Registry | `ai-agent-registry` |
| `/policies` | Policy Governance | `policy-governance` |
| `/decisions` | Decision Intelligence | `decision-intelligence-detail` |
| `/decisions/[id]` | Decision Investigation | `decision-investigation` |
| `/simulations` | Simulation Engine Workspace | `simulation-engine-workspace` |
| `/status` | System health (Phase 0) | — |

`/trust-engine`, `/explain`, `/ledger`, `/analytics`, `/alerts` and `/settings`
appear in the nav and route to placeholders — they have no design yet and are
marked "soon" in the sidebar.

The `executive-overview` export is ~90% identical to `atlas-control-center`
(which supersedes it as "Refined"), so it is not built as a separate route.

Every data-backed screen reads live from the API. If the backend is down the
route renders an explicit "Backend unavailable" panel rather than crashing.

## API

All responses are camelCase, so `apps/web/src/lib/types.ts` consumes them with
no mapping layer.

| Endpoint | Returns |
| --- | --- |
| `GET /api/v1/health` | Service + dependency health |
| `GET /api/v1/dashboard` | Aggregated metrics, composite trust, pipeline, activity |
| `GET /api/v1/agents` · `/{id}` | Agent registry with trust factors |
| `GET /api/v1/decisions` · `/{id}` | Decisions with policy evidence and investigation |
| `GET /api/v1/policies` | Policy ledger |
| `GET /api/v1/simulations` · `/{id}` | Simulation runs with predicted outcomes |
| `GET /api/v1/activity` | Governance activity feed |
| `GET /api/v1/trust/overview` | Estate trust, band distribution, drift watchlist |
| `GET /api/v1/trust/agents/{id}` | Score breakdown, history, drift, forecast, explanation |
| `POST /api/v1/trust/recompute` | Re-evaluate every agent and snapshot the result |

## Trust Engine

An agent's score is computed, never stored as a given:

```
score = weighted mean of trust factors − anomaly penalty
```

- **Factors** are normalised by weight, so adding a factor does not silently
  rescale every agent.
- **Anomaly penalty** deducts points for blocked and escalated decisions inside
  a 7-day window, capped so one bad week cannot erase a long record.
- **Drift** compares an agent against *its own* baseline. Comparing across
  agents would only measure that they are different agents.
- **Lifecycle** follows from the evaluation: a steep decline means `anomaly`
  even when the absolute score still looks respectable, and an agent climbing
  out of trouble passes through `recovery` before it is trusted again.
- **Forecast** is a least-squares projection over that agent's own snapshots,
  and is `null` below three samples rather than a guess.

Every evaluation returns an `explanation` — the arithmetic in plain language.

`trust_snapshots` is what makes any of this possible: without stored history
there is no baseline, no drift, and no honest forecast.

### Data model notes

- **Money is `Numeric(16,2)`**, never float, so amounts round-trip exactly. It is
  serialised as a JSON number for the client.
- **`decisions.investigation` and `simulation_runs.request` are `JSONB`** — their
  shape varies per action type and they are always read alongside their parent
  row, so sparse relational tables would buy nothing.
- **`policy_checks.policy_name` is denormalised on purpose.** Policies are
  versioned and renamed; an audit record must show the name as it was at the
  time of the decision.
- **`compositeTrust.predicted` is `null`.** The trend samples trust across
  different agents, so extrapolating it would be misleading. Real forecasting
  arrives with the Trust Engine in Phase 3.

---

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Foundation — monorepo, design tokens, health check wired end to end | ✅ |
| 1 | Frontend shell — Stitch screens as real React routes on typed mock data | ✅ |
| 2 | Data model & API — core entities, migrations, live console | ✅ |
| 3 | Trust Engine — scoring, history, drift, lifecycle, forecasting | ✅ |
| 4 | Policy Brain — policy authoring + evaluation | |
| 5 | Simulation Engine — pre-execution outcome prediction | |
| 6 | Decision pipeline & governance ledger | |
| 7 | Auth, seed data, deployment | |
