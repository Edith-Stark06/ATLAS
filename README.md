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

Phase 1 renders everything from typed fixtures in `apps/web/src/lib/mock-data.ts`.
Those shapes (`apps/web/src/lib/types.ts`) are the contract the API will satisfy
in Phase 2.

---

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Foundation — monorepo, design tokens, health check wired end to end | ✅ |
| 1 | Frontend shell — Stitch screens as real React routes on typed mock data | ✅ |
| 2 | Data model & API — core entities, migrations, CRUD | |
| 3 | Trust Engine — dynamic trust scoring | |
| 4 | Policy Brain — policy authoring + evaluation | |
| 5 | Simulation Engine — pre-execution outcome prediction | |
| 6 | Decision pipeline & governance ledger | |
| 7 | Auth, seed data, deployment | |
