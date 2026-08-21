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

Use `python -m app` rather than invoking `uvicorn` directly. On Windows,
uvicorn picks a `ProactorEventLoop` for a single-process server and a
`SelectorEventLoop` when `--reload` forks a subprocess — and psycopg3's async
driver only works on the latter. `app/__main__.py` passes the loop factory
explicitly so the database works either way; running `uvicorn app.main:app`
by hand without `--reload` fails on the first query. Entrypoints that reach
the database through `asyncio.run` (alembic, the seeder, pytest) use the
policy shim in `app/core/compat.py` instead.

Auto-reload is off by default (`API_RELOAD=true` to enable) — the reloader's
child process can outlive an abruptly killed parent and keep serving stale
code from port 8000, which looks exactly like "my changes aren't taking
effect".

Apply migrations:

```bash
cd apps/api && .venv/Scripts/python.exe -m alembic upgrade head
```

Train the ML models (optional — the API works without this, falling back to
the Phase 3 heuristic; see [Trust Engine](#trust-engine)):

```bash
cd apps/api && .venv/Scripts/python.exe -m app.ml.train
```

Load the reference dataset — do this *after* training so the seeded history
is scored by the trained model instead of the heuristic:

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

## Routes

The marketing page owns `/`; the console lives under `/console`.

| Route | Screen | Source |
| --- | --- | --- |
| `/` | Landing page — hero, governance pipeline, capabilities | built in Next.js |
| `/console` | Control Center dashboard | `atlas-control-center` |
| `/console/agents` | AI Agent Registry | `ai-agent-registry` |
| `/console/policies` | Policy Governance + rule builder | `policy-governance` |
| `/console/decisions` | Decision Intelligence | `decision-intelligence-detail` |
| `/console/decisions/[id]` | Decision Investigation | `decision-investigation` |
| `/console/simulations` | Simulation Engine + scenario workspace | `simulation-engine-workspace` |
| `/console/ledger` | Governance Ledger — chain integrity + audit records | built in Next.js |
| `/console/trust-engine` | Trust Engine | built in Next.js |
| `/console/status` | System health | — |

`/console/explain`, `/analytics`, `/alerts` and `/settings` appear in the nav
and route to placeholders — they have no design yet and are marked "soon" in
the sidebar.

The `executive-overview` export is ~90% identical to `atlas-control-center`
(which supersedes it as "Refined"), so it is not built as a separate route.

Every data-backed screen reads live from the API. If the backend is down the
route renders an explicit "Backend unavailable" panel rather than crashing.
The landing page is fully static and needs no backend at all.

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
| `GET /api/v1/trust/model-info` | Trained model provenance and baseline-vs-learned metrics |
| `POST /api/v1/trust/simulate` | Score a hypothetical decision with the trained outcome classifier |
| `GET /api/v1/policy/vocabulary` | Fields, operators and effects a rule may use |
| `GET /api/v1/policy/policies` · `/{id}` | Policies with their active rule and version history |
| `POST /api/v1/policy/policies/{id}/versions` | Append an immutable rule version |
| `POST /api/v1/policy/evaluate` | Run the active policy set against a hypothetical decision |
| `POST /api/v1/policy/simulate` | Replay a candidate rule over recorded decisions |
| `POST /api/v1/simulation/run` | Evaluate a proposed action end to end — not persisted |
| `POST /api/v1/simulation/rebuild` | Regenerate every stored run from the current engine |
| `POST /api/v1/decisions/execute` | Run an action through the pipeline and commit it |
| `GET /api/v1/ledger` | Audit records, newest first (`kind`, `subjectId`, `limit`) |
| `GET /api/v1/ledger/verify` | Recompute every hash and check every link |
| `GET /api/v1/ledger/stats` | Chain head, counts by kind, model fingerprint |
| `GET /api/v1/ledger/{seq}` | One audit record with its pinned evidence |

## Trust Engine

An agent's score is **computed**, never stored as a given. When a trained
model is present (`apps/api/app/ml/artifacts/`), it is the primary source;
otherwise the system falls back to a deterministic heuristic — the same
0–100 scale either way, so nothing else in the pipeline needs to know which
produced a given score.

```
heuristic fallback: score = weighted mean of trust factors − anomaly penalty
ml (primary):        score = 100 × P(next decision is compliant), from a
                      logistic regression trained on labelled outcomes
```

- **Factors** are normalised by weight in the heuristic path, so adding a
  factor does not silently rescale every agent.
- **Anomaly penalty** deducts points for blocked and escalated decisions inside
  a 7-day window, capped so one bad week cannot erase a long record.
- **Drift** compares an agent against *its own* baseline. Comparing across
  agents would only measure that they are different agents.
- **Lifecycle** follows from the evaluation: a steep decline means `anomaly`
  even when the absolute score still looks respectable, and an agent climbing
  out of trouble passes through `recovery` before it is trusted again.
- **Forecast** is a least-squares projection over that agent's own snapshots,
  and is `null` below three samples rather than a guess.

Every evaluation returns an `explanation` — the arithmetic in plain language,
plus (when ML-scored) a SHAP-derived per-factor attribution.

`trust_snapshots` is what makes any of this possible: without stored history
there is no baseline, no drift, and no honest forecast.

### ML Trust Engine (Phase 4)

Three trained models, each replacing a Phase 3 heuristic, evaluated against
it rather than assumed to be better:

| Component | Replaces | Model | Result vs. heuristic |
| --- | --- | --- | --- |
| Trust scoring | Hand-set factor weights | Logistic regression | AUC 0.632 → 0.670 (+6.1%) |
| Drift detection | Fixed threshold vs. population mean | Per-agent Isolation Forest | F1 0.263 → 0.335 (+27%) |
| Outcome simulation | Fixed percentages for every decision | Gradient-boosted classifier | Log-loss 1.005 → 0.946 (−6%) |

```bash
cd apps/api && .venv/Scripts/python.exe -m app.ml.train
```

Trains on a synthetic dataset (no real decision history exists yet to train
on) with disclosed, inspectable structure — see
`apps/api/app/ml/dataset.py` and, for the full methodology and the
patent-relevant technical-effect argument, **`docs/patent/
technical-disclosure.md`**. Re-seeding after training
(`python -m app.seed --reset`) backfills history *scored by the trained
model*, so historical and live scores stay methodologically coherent — see
§5.5 of the disclosure for why this matters.

Artifacts are gitignored (`apps/api/app/ml/artifacts/`) — regenerate them
locally rather than committing binaries; `metrics.json` there is the
canonical source for the numbers in the table above.

### Data model notes

- **Money is `Numeric(16,2)`**, never float, so amounts round-trip exactly. It is
  serialised as a JSON number for the client.
- **`decisions.investigation` and `simulation_runs.request` are `JSONB`** — their
  shape varies per action type and they are always read alongside their parent
  row, so sparse relational tables would buy nothing.
- **`policy_checks.policy_name` is denormalised on purpose.** Policies are
  versioned and renamed; an audit record must show the name as it was at the
  time of the decision.
- **`compositeTrust.predicted`** is a genuine least-squares projection over
  the estate's own trust-snapshot history (one point per evaluation round,
  averaged across agents) — `null` below three rounds rather than a guess.
  Phase 2 returned `null` unconditionally because that history didn't exist
  yet; Phase 3 introduced `trust_snapshots`, which is what made this real.

## Policy Brain

Rules are **data, not code** — a list of conditions over a closed field
vocabulary, combined with `all`/`any`, producing an effect:

```
IF Trust Score < 70 AND Amount (USD) > 5000
THEN require human review
Applies to: all agents
```

That representation is what makes rules storable, versionable, diffable, and
simulatable — none of which is possible if a policy is a hand-written branch.

- **Closed vocabulary.** A rule may only reference the fields in
  `EVALUABLE_FIELDS` (`app/services/policy_engine.py`). No arbitrary
  attribute access, and the authoring UI builds its pickers from
  `GET /policy/vocabulary` so it cannot drift from what the engine accepts.
- **Immutable versions.** Editing a policy appends a `policy_versions` row
  and repoints `policies.active_version_id`. A decision recorded months ago
  stays explainable against the exact rule text that produced it.
- **Most restrictive wins.** When several policies match, `block` beats
  `require_human_review` beats `allow` — a permissive rule can never
  silently override a block.
- **No match means allow.** Policies restrict an otherwise-permitted action.
  Defaulting to `block` would mean an empty policy set halts the estate,
  which is not a safe failure mode for rules edited live.
- **Missing values are "unevaluable", not "false".** A card freeze has no
  amount, so an amount-threshold condition is reported as skipped with a
  reason. Conflating "we could not tell" with "we checked and it passed"
  would make the audit trail misleading.
- **Simulate before deploy.** `POST /policy/simulate` replays a candidate
  rule over recorded decisions and reports what it catches. It evaluates the
  rule *alone*, so a decision it misses falls through to `allow` even when
  other policies still restrict it — the console labels that a coverage gap,
  not an outcome reversal.

## Simulation Engine

Trust says how much an agent is worth believing. Policy says what the rules
permit. The Simulation Engine answers the question those two leave open:
**if this action ran right now, what would happen?** It runs before anything
executes, so the answer is still useful.

`POST /simulation/run` takes a proposed action and returns one
recommendation with the evidence behind it: the trained classifier's
probability over `approved` / `escalated` / `blocked`, the full policy trace,
and what it costs.

- **Policy is a hard constraint; the model is advisory.** A `block` or
  `require_human_review` effect decides the recommendation outright and the
  response is flagged `policyForced`. A statistical prediction must never
  unblock something the rules explicitly forbid — however confident it is.
  Above that, the model may still escalate what the rules permit, when
  combined `escalated + blocked` probability crosses
  `ADVERSE_ESCALATION_THRESHOLD`.
- **Money follows the recommendation, not the probabilities.** Once the
  verdict is to block or hold, `expectedExposureUsd` is `0` and the amount
  appears in `withheldUsd`. Quoting a probability-weighted figure there would
  report exposure the system is actively preventing — reading
  "blocked, expected exposure $3,236" is nonsense.
- **The counterfactual is reported too.** `unconstrainedExposureUsd` is what
  an *unpoliced* system would expose on average. The gap between it and
  `expectedExposureUsd` is what the governance layer is buying, in dollars.
- **Nothing is persisted.** A what-if must not appear in the audit trail
  beside decisions that actually happened. Stored runs are written only via
  `rebuild`, which attaches them to real decisions.
- **A missing agent is a 404, not a default.** Scoring a typo'd agent ID
  against a fallback trust score would hand back a confident verdict for an
  agent nobody evaluated. `agentId: null` remains valid and means a
  deliberately unattributed scenario.
- **No trained model reads as "no signal".** Without an artifact on disk the
  probabilities are an even three-way split and `modelBacked` is `false`,
  rather than a confident-looking guess.

The console workspace at `/console/simulations` drives this live: pick an
agent, set an amount and a risk score, and override trust to ask "what if
this agent's score dropped to 40?" — the one question the stored history
cannot answer.

## Decision Pipeline & Governance Ledger

Everything before this evaluated hypotheticals. `POST /decisions/execute` is
the committing path: it runs the same pre-execution evaluation, then records
what was decided, why, and against which rules and model.

Order is not arbitrary. Trust, policy and simulation all run *before*
anything is written, so an action that is going to be blocked is blocked on
evidence gathered beforehand, not justified afterwards. The decision, its
policy checks, the simulation that decided it and the ledger entry are
written in **one transaction** — a decision that exists without an audit
record is precisely the failure this system is built to prevent.

Callers branch on `executed`, a plain boolean, rather than string-matching
the outcome. A replayed `decisionId` — the normal result of an enterprise
system retrying after a timeout — returns **409**, not a second decision and
not a raw database error.

### The ledger is a hash chain

Each entry commits to the one before it:

```
entry_hash = sha256(version ⧺ seq ⧺ prev_hash ⧺ kind ⧺ subject_id ⧺ recorded_at ⧺ canonical_json(payload))
```

Position, linkage, type, subject and time are all inside the preimage — not
just the payload — so entries cannot be reordered or reassigned to a
different decision without breaking a hash.

- **Tamper-evident, not tamper-proof.** Anyone with database access can still
  edit a row. What they cannot do is make it verify: the edit invalidates
  that entry's hash and every hash after it. `GET /ledger/verify` recomputes
  the whole chain on each request — a verification result that is itself just
  a database row would prove nothing. Real tamper-*proofing* needs the head
  hash anchored somewhere the same operator does not control, which is a
  deployment concern rather than a schema one.
- **One canonical serialisation.** Sorted keys, no whitespace, non-JSON types
  rejected rather than coerced. If the same evidence can serialise two ways,
  a mismatch proves nothing.
- **Money is a string, fixed to cents.** Hashing a float would make the
  record depend on repr precision, and `"12450.5"` must not be a second
  spelling of the `12450.50` in the column.
- **The pinned evidence is what gets recomputed.** Each decision entry holds
  the inputs *actually used* (defaults resolved, not the caller's nulls), the
  rule **versions** in force, a SHA-256 fingerprint of the trained artifacts,
  the predicted distribution, and the exposure. A policy renamed or
  re-authored later cannot change what a past decision is judged against.
- **`subject_id` is deliberately not a foreign key.** An audit record must
  outlive the thing it describes; an FK would either block the deletion or
  cascade the history away with it.

Known limit, stated rather than papered over: `append` reads the current head
and writes the next entry, so concurrent appends can fork the chain. Single
-writer development is fine; a busy deployment needs a serialisable
transaction or an advisory lock on the head.

---

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Foundation — monorepo, design tokens, health check wired end to end | ✅ |
| 1 | Frontend shell — Stitch screens as real React routes on typed mock data | ✅ |
| 2 | Data model & API — core entities, migrations, live console | ✅ |
| 3 | Trust Engine — scoring, history, drift, lifecycle, forecasting | ✅ |
| 4 | ML Trust Engine — trained models replacing every Phase 3 heuristic | ✅ |
| 5 | Policy Brain — versioned rules, evaluation, pre-deploy simulation | ✅ |
| 6 | Simulation Engine — pre-execution outcome prediction | ✅ |
| 7 | Decision pipeline & governance ledger — hash-chained audit records | ✅ |
| 8 | Auth, seed data, deployment | |
