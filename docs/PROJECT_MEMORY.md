# ATLAS — Project Memory

Complete context handoff. Written 2026-08-24, updated through Phase 16
(2026-09-03) — Phase 15 operational readiness, the real-data risk model,
agent registration, the real-time activity feed, the IT Ops vertical pack
(closing out all five mentor-feedback directions), and Phase 16 scale &
lifecycle all landed since the previous 2026-08-24 write-up.

Repo: https://github.com/Edith-Stark06/ATLAS · branch `main` · local path
`D:\Documents\Projects\ATLAS`

---

## 1. What this is

**ATLAS — Adaptive Trust & Lifecycle Assurance System.** A governance layer
that decides whether autonomous financial agents can be trusted *before* they
act.

The distinction it exists to make:

> Traditional governance asks *"is this agent authorized to perform this
> action?"* ATLAS asks *"should this agent be trusted to perform this action,
> **right now**, under **these** circumstances?"*

Every action passes through a pre-execution pipeline:

```
Agent Request → Trust Engine → Policy Brain → Simulation Engine
             → Governance Decision → Explain AI → Governance Ledger → Execution
```

It is also an **invention disclosure project** — `docs/patent/technical-disclosure.md`
is maintained alongside the code as a filing-ready document for a patent
agent. Design decisions are made and documented with that in mind.

---

## 2. Stack & layout

| Layer | Technology |
| --- | --- |
| Web | Next.js **16** (App Router), React 19, TypeScript, Tailwind v4 |
| API | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic |
| Data | PostgreSQL (container tag `postgres:16`), Redis 7 |
| ML | scikit-learn, SHAP, joblib |
| Auth | PyJWT (HS256) + argon2-cffi |
| Design | Tokens exported from Stitch (`stitch_export/`) |

```
apps/
  web/                    Next.js frontend
    src/app/console/      the console (agents, policies, decisions, …)
    src/lib/api.ts        SERVER-ONLY api client (reads session cookie)
    src/lib/api-client.ts BROWSER api client (goes via /api/atlas proxy)
    src/proxy.ts          Next 16's renamed "middleware"
  api/
    app/services/         engines (pure) + services (DB)
    app/api/routes/       FastAPI routers
    app/ml/               training + artifacts
    alembic/versions/     5 migrations
infra/
  docker-compose.yml      Postgres + Redis (dev)
  docker-compose.prod.yml full stack (api, web, migrate, db, redis)
docs/patent/              invention disclosure
stitch_export/            source design screens
```

**Architectural convention throughout:** `*_engine.py` is pure functions over
plain values (no DB, no I/O, exhaustively unit-testable). `*_service.py` does
the database work and calls the engine. Routes are thin.

---

## 3. Running it

```bash
cp .env.example .env
npm run db:up                                            # Postgres :5433, Redis :6380
cd apps/api && python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m app.ml.train                 # optional; heuristic fallback exists
.venv/Scripts/python.exe -m app.seed --reset             # AFTER training
.venv/Scripts/python.exe -m app                          # API on :8000
npm run dev                                              # web on :3000
```

**Login:** `admin@atlas.local` / `atlas-dev-admin` (role `admin`).
Created by the seeder **only when no users exist**. `--reset` reloads the
governance dataset and deliberately leaves credentials alone.

### Non-obvious operational facts

- **Ports are 5433 / 6380**, not the defaults — deliberately, so ATLAS never
  collides with another local project.
- **Always `python -m app`, never bare `uvicorn`.** On Windows uvicorn picks a
  `ProactorEventLoop` for a single-process server, and psycopg3's async driver
  **cannot use it** — every query fails. `app/__main__.py` passes the loop
  factory explicitly. Entrypoints reaching the DB via `asyncio.run` (alembic,
  seeder, pytest) use the policy shim in `app/core/compat.py`.
- **`API_RELOAD` is off by default.** The reloader's child can outlive an
  abruptly killed parent and keep serving stale code from :8000 — looks
  exactly like "my changes aren't taking effect".
- **Docker Desktop on this machine starts stopped.** If Postgres is
  unreachable, start Docker Desktop and wait ~15s.

---

## 4. Build phases — all complete

| # | Phase | Commit |
| --- | --- | --- |
| 0 | Foundation — monorepo, design tokens, health check | `b11037a` |
| 1 | Frontend shell — Stitch screens as React on typed mocks | `b11037a` |
| 2 | Data model & API — entities, migrations, live console | `f4070fa` |
| 3 | Trust Engine — scoring, history, drift, lifecycle, forecast | `cc0848d` |
| 4 | ML Trust Engine — trained models replace every heuristic | `f7e7037` |
| 5 | Policy Brain — versioned rules, evaluation, pre-deploy sim | `6651cbc` |
| 6 | Simulation Engine — pre-execution outcome prediction | `82c25e6` |
| 7 | Decision pipeline & governance ledger — hash chain | `1f692df` |
| 8 | Auth, roles, actor attribution, containerised deploy | `f502c4d` |
| 9 | Explain AI — drivers, rule evidence, counterfactuals | `1493b60` |
| 10 | Governance Analytics — trends, latency, policy hot spots | `fb515ca` |
| 11 | Agent Benchmark — cohort ranking, change attribution | `b7fec78` |
| 12 | Capacity Planning — growth constraints, binding limit | `bea097b` |
| 13 | Vertical packs — domain vocabulary and rules | `729922d` |

Remaining console placeholders: **Alerts**, **Settings**.

---

## 5. The core subsystems

### Trust Engine (`trust_engine.py`, `trust_service.py`)

An agent's score is **computed, never stored as given**.

```
ML (primary):   score = 100 × P(next decision is compliant)   ← logistic regression
heuristic:      score = weighted mean of factors − anomaly penalty
```

Five factors: `behavior` .22, `policy` .24, `risk` .20, `context` .14,
`history` .20.

- Label is **forward-looking** — "was the agent's *next* decision adverse" —
  so the score predicts risk rather than describing the past.
- Falls back to the heuristic when no artifact is present, with **no branch
  visible to the caller**.
- Anomaly window: **7 days**. Per-agent Isolation Forest for drift, fitted
  only on the features the trust model itself found informative.

Trained metrics (`app/ml/artifacts/metrics.json`, 320 agents × 60 steps):

| Model | Baseline | Learned |
| --- | --- | --- |
| Trust (AUC) | 0.632 | **0.670** (+6.1%) |
| Drift (F1) | 0.263 | **0.335** |
| Simulation (accuracy) | 0.531 | **0.568** |
| Simulation (log loss) | 1.005 | **0.946** |

#### Real-Data Risk Model (`app/ml/train_risk_model.py`) — added 2026-09-02

A **fourth model**, trained on real data instead of `dataset.py`'s
synthetic generator — for the patent disclosure's technical-effect
evidence, not something the live decision pipeline currently calls.
`docs/patent/technical-disclosure.md` §5.9/§6.4 has the full writeup;
summary:

- **Dataset**: "Credit Card Fraud Detection" (Worldline / ULB Machine
  Learning Group) — 284,807 real European cardholder transactions,
  September 2013, 492 (0.172%) labelled fraud. Fetched from OpenML
  (`python -m app.ml.fetch_real_data`, no account needed), gitignored
  (~150MB, ODbL v1.0 — not ours to redistribute), validated (row count,
  fraud count, column layout) before every use.
- **Why a fourth model rather than retraining `SimulationModel`**: of the
  31 columns, only `Amount`/`Time` are interpretable — the other 28
  (`V1`..`V28`) are PCA components, and there's no persistent per-cardholder
  identity across rows. That's enough to train a real fraud/risk classifier,
  but *not* enough to supply `SimulationModel`'s governance-context features
  (`policy_pass_rate`, `authority_level`, ...) — no public transaction
  dataset could, without fabricating them. `RiskModel` (`app/ml/models.py`)
  is therefore new and separately scoped, not a drop-in replacement.
- **Results** (213,605 train / 71,202 test, stratified): ROC-AUC 0.500 →
  0.967, average precision 0.002 → 0.777, precision/recall at threshold 0.5
  = 0.528/0.829. Log-loss is reported too despite being *worse* for the
  learned model (0.013 → 0.022) — a known property of log-loss at this
  class ratio, not a modelling defect, and stated plainly rather than
  omitted (see §6.4 for why).
- **Real bug found**: OpenML's CSV export wraps the `Class` label in literal
  single quotes (`'0'`/`'1'`), an ARFF-conversion artifact. Read naively
  this produces string labels scikit-learn accepts without error but that
  silently break every downstream numeric computation. Caught by validating
  against the dataset's published row/fraud counts before training, not by
  inspection — `fetch_real_data.py`'s whole reason for existing rather than
  a bare `pd.read_csv` in the training script.
- Tests (`tests/test_ml_train_risk_model.py`) skip when the dataset hasn't
  been fetched, same pattern as an unreachable Postgres elsewhere in this
  suite — not part of CI (no fetch step added there; 150MB on every run
  isn't worth it for something CI doesn't otherwise exercise).

#### Agent Registration (`POST /agents`) — added 2026-09-02

Closed a real gap found while discussing "real" agents: there was no way to
register one through the API at all — every agent in the system existed
only because `app/seed.py`/`seed_cohort.py`/`seed_domains.py` inserted its
row directly. `POST /agents` (`governance.py`, `RequireAdmin`) is the
missing piece: takes `id`/`name`/`capability`/`owner`/`model`/
`authority_level` and optional starting factor scores (0-100, any factor
left unset defaults to a neutral 50 — a new agent has no track record, so
nothing is asserted that hasn't been earned). `trust_score` is **derived**
via `trust_engine.compute_base_score`, never accepted from the caller —
the same "computed, never stored as given" rule every other trust score in
this system follows. Starts in `lifecycle=onboarding` with zero decisions.

Pulled `FACTOR_LABELS`/`FACTOR_WEIGHTS` into `trust_engine.py` as the
canonical source (used by the new endpoint) rather than adding a fourth
copy — `seed.py`, `seed_cohort.py`, and `seed_domains.py` each already
duplicate these constants locally; left untouched as pre-existing, working
code outside this change's scope, but worth fixing centrally if anyone
touches factor weights again.

Tests (`test_governance.py`) use a `cleanup_test_agents` fixture that
deletes exactly the agent rows a test creates — safe and complete here
specifically because a freshly-registered agent has no decisions or ledger
entries yet. That would **not** be true of a demo agent that goes on to
*commit* real decisions: each one writes a permanent, hash-chained ledger
entry that cannot be deleted afterward without breaking the chain for
everything decided after it — deliberately, that's the tamper-evidence
mechanism (§5 above) working as designed. A one-off live demo (register →
mint a key → commit ~30 real decisions → check `/trust/agents/{id}` and
`/benchmark/cohorts/{capability}`) is therefore run manually, not added to
the automated suite, and its agent stays in the seeded estate afterward
rather than being cleaned up.

### Policy Brain (`policy_engine.py`, `policy_service.py`)

Rules are **immutable versioned records**. Fields: `trust_score`,
`risk_score`, `amount_usd`, `authority_level`, `agent_lifecycle`,
`capability`, `hour_utc`. Effects: `allow` / `require_human_review` / `block`.

- A missing value makes a condition **unevaluable, not false** — a card freeze
  has no amount, and an amount-threshold rule must not fire on it.
- `POST /policy/simulate` replays a *candidate* rule over recorded decisions
  before deployment.

### Simulation Engine (`simulation_engine.py`)

- **Policy is a hard constraint; the model is advisory.** A blocking rule
  overrides a confident model, always.
- **Money follows the recommendation, not the probabilities.** A blocked
  action's expected exposure is `0`, not `p(approve) × amount`.
- Reports `withheld_usd` and `unconstrained_exposure_usd` so the value of
  governance is visible rather than implied.

### Decision Pipeline + Governance Ledger (`decision_service.py`, `ledger.py`)

`POST /decisions/execute` is the committing path. Decision, policy checks,
simulation and ledger entry are written in **one transaction** — a decision
without an audit record is the failure the system exists to prevent.

The ledger is a hash chain:

```
entry_hash = sha256(version ⧺ seq ⧺ prev_hash ⧺ kind ⧺ subject_id
                    ⧺ recorded_at ⧺ canonical_json(payload))
```

- **Tamper-evident, not tamper-proof** — stated everywhere, including in the
  UI. Anyone with DB access can edit a row; they cannot make it verify.
- Canonical JSON: sorted keys, no whitespace, non-JSON types **rejected not
  coerced**.
- Money is a **fixed-point string** — hashing a float would make the record
  depend on repr precision.
- Pins the inputs *actually used*, the rule **versions** in force, a SHA-256
  of the model artifacts, and the **actor**.
- A replayed `decisionId` → **409**, not a second decision or a raw 500.
- Known limit, documented: `append` reads the head then writes, so concurrent
  appends can fork the chain. Needs a serialisable transaction or advisory
  lock for multi-writer.

### Auth (`security.py`, `auth_service.py`, `deps.py`)

Two credential types → one internal `Actor`.

| Credential | For | Hashing |
| --- | --- | --- |
| Password → JWT | Console operators | **Argon2id** (slow, memory-hard) |
| `atlas_sk_…` key | Agents / services | **SHA-256** (fast) |

The asymmetry is deliberate: passwords are low-entropy so each guess must be
expensive; an API key is 256 bits of `secrets` randomness, so a slow hash
would only add latency to every agent request.

Roles: `viewer` → `operator` → `admin`. **Role is re-read per request**, never
trusted from the token claim. JWT algorithms are **pinned** (blocks `alg:none`
and HMAC/RSA confusion). Login answers identically for unknown account and
wrong password. Keys are **revoked, not deleted** (their prefix names the
actor in past audit records). An agent-bound key cannot act for another agent.

Console: token in an **httpOnly cookie**, so page scripts cannot read it.
Client components therefore go through `/api/atlas/[...path]`, which attaches
the token server-side. `src/proxy.ts` redirects unauthenticated navigation but
**is not the security boundary** — the API validates every request.

### Explain AI (`explanation_engine.py`)

Reconstructed from the ledger's **pinned evidence**, not current state.
Re-evaluating an old decision against today's rules would produce a confident
explanation of a decision that never happened.

- **Policy boundaries are exact** (arithmetic from the rule threshold).
- **Model boundaries are searched** — scanning the feature's real range, *not*
  bisecting, because gradient boosting is non-monotonic and a binary search
  returns a plausible boundary that does not exist.
- **Every suggestion is replayed against the whole rule set** and kept only if
  the combined verdict changes. Found by looking at the rendered page: with
  two rules binding, "amount ≤ $2,000" was exactly right about its own rule
  and useless as advice.
- **`changesTo` is computed, not assumed** — clearing a block often leaves a
  review requirement, so it is frequently `escalated`, not `approved`.

### Analytics (`analytics_engine.py`)

- **Percentiles, not means** — nearest-rank, so every figure is a request that
  really happened. Live seed shows p50 14ms / mean 109ms / p99 1913ms.
- **Rates carry their denominator** — 8% of 12 is noise, 8% of 12,000 is a
  finding.
- Quiet days rendered, not skipped. Empty buckets reported. `0/0` → 0%, not
  100%. Amount-less actions excluded from exposure.
- **Dead-rule detection**: a policy evaluated ≥20 times that never matched is
  mis-scoped or redundant — but not flagged before it has been tested.

### Agent Benchmark (`benchmark_engine.py`) — newest

Ranks agents doing the **same job** on five weighted criteria: security .30,
compliance .25, efficiency .20, reliability .15, speed .10.

- **Only comparable things compared** — cross-capability ranking raises.
- **Absolute scores, never normalised to the cohort** (normalising manufactures
  a worst member at 0 by construction).
- Security counts blocks but **ignores escalations** (an escalation is the
  system working). Efficiency counts escalations (they cost human time).
  Reliability measures trust *variance*.
- **Unproven agents cannot be the benchmark.** Found in the rendered ranking:
  a 1-decision agent was topping a cohort of 11 and setting the bar everyone
  else was measured against.
- **Mechanism ranking**: score change decomposed per factor, split into "the
  factor moved" vs "its weight was re-tuned". Unexplained remainder reported
  as a **residual**, never spread across factors. A large residual is the
  useful signal — the model judged the agent differently for reasons its
  inputs do not capture.

Seeded cohort: `Customer Servicing`, 10 agents in `app/seed_cohort.py`, each
tuned to fail on a *different* criterion (fast-but-careless,
slow-but-impeccable, escalates-everything, unstable, brand-new).

### Capacity Planning (`capacity_engine.py`) — newest

`POST /capacity/plan` projects what growing a job would demand of governance.
The output is the **binding constraint**, not a headline number.

- Constraints: human review (reviewer-days), trusted agent capacity, latency
  budget. `binding` is the one with the *least headroom* — so a constraint can
  be satisfied and still be the limit.
- **Safety is gated directly, not via the composite.** The seeded cohort's
  worst agent on security *and* compliance still scored 84.5 composite because
  it was the fastest. Speed does not offset a compliance problem.
- Latency measured only across agents actually taking load — otherwise one slow
  agent nobody is scaling vetoes every plan.
- Growth capped at 2× per agent. `unallocatedDaily` surfaces target volume
  nobody can safely take.
- Assumptions and out-of-scope both travel in the response. ATLAS observes
  decisions, not servers — it does not size infrastructure or cost.

### Vertical Packs (`app/domains/`) — newest

Domain-specific rule vocabulary without forking the engine.

- `evaluable_fields()` = `CORE_FIELDS` + every registered pack. Closed, not
  open: an unknown field is still refused.
- `PolicyContext.attributes` carries domain values. **Absent stays absent** —
  a funds rule on a travel decision finds no concentration and is unevaluable,
  not false.
- Core wins a name clash; field names asserted unique across packs at import.
- Shipped rules go through the ordinary parser and versioning. Tests assert
  each references only core or its own domain's fields.
- Packs: investments, travel, booking, **it_ops** (added 2026-09-02, closing
  the last unaddressed mentor-feedback item — system/log analysis and
  transaction-capacity scaling in banks). Seeded with one agent per
  capability, carrying the domain attributes their rules read.
- **Real gap found while adding it_ops, pre-existing for every pack, not
  specific to this one**: there is no live way to submit domain attributes
  through the real API. `ExecuteDecisionRequest`
  (`POST /decisions/execute`) and `SimulateActionRequest`
  (`POST /simulation/run`) both have no `attributes` field — grepped for
  it across `app/schemas/ledger.py`, `app/schemas/simulation.py`,
  `decision_service.py`, `simulation_service.py`: zero hits. A vertical
  pack's rules are fully real and correctly enforced *if* a decision
  carries matching attributes, but today the only way a decision ever
  does is `app/seed_domains.py` writing them directly into the
  `investigation` JSONB blob — not something any live caller, human or
  agent, can do yet for any of the four packs. Verified the it_ops rules
  themselves are correct by evaluating them directly against
  `policy_engine.evaluate_rule`/`combine` (now `tests/test_domains.py`'s
  IT-Ops-specific tests), not by trusting a live round trip that doesn't
  exist. Fixing this — threading `attributes` through the request schemas
  and into `PolicyContext` construction — is real, separate scope
  touching every pack at once, not something to slip into one pack's
  addition; noted here as a known open issue instead.

### Real-Time Activity Feed (`app/services/activity_stream.py`) — added 2026-09-02

The console's "Live" badge and "Streaming from ATLAS API" footer predate
this — cosmetic labels on a server-rendered, request/response-only page.
`ActivityItem` ("An entry in the live governance activity feed") also
predates this, but nothing ever wrote to it at runtime; every row that
ever existed came from `app/seed.py`'s demo data. Both gaps close together:

- `decision_service.execute` now writes a real `ActivityItem` in the same
  transaction as the decision (approved→success, escalated→warning,
  blocked→danger), then — only *after* `db.commit()` succeeds — publishes
  it to a Redis Pub/Sub channel (`atlas:activity`). Never announces an
  event for data that didn't actually persist. Fails open on a Redis error,
  same rule as the rate limiter: a live-feed hiccup must not turn a
  successfully committed decision into a failed request.
- `GET /activity/stream` (SSE, `RequireViewer`) subscribes and forwards.
- **SSE, not WebSockets** — decided from Next.js 16.3.1's actual docs, not
  assumed: Route Handlers document SSE as supported (`ReadableStream`
  response); WebSockets are explicitly unsupported through that same
  convention. The need is one-directional anyway.
- **Redis Pub/Sub, not an in-process bus** — multiple API replicas are
  already anticipated elsewhere (`rate_limiter.py`'s docstring,
  `docker-compose.prod.yml`'s migrate-service comment about replica races);
  an in-process bus would miss events committed on a different replica
  than the one a browser's stream is attached to.
- **A dedicated Next.js proxy route** (`api/atlas/stream/route.ts`), not a
  branch in the existing generic one — that one fully buffers both
  directions (`await request.text()` / `await upstream.text()`) and would
  hang forever on a connection that's designed to never end. The dedicated
  route pipes `upstream.body` straight through instead. Auth is solved the
  same way every other browser→API call already is: a browser-native
  `EventSource` cannot set an `Authorization` header, so it doesn't try to
  — it hits this same-origin route, the browser sends the session cookie
  automatically, and the route attaches the real credential server-side.
- **First client component with an ongoing subscription** in this app
  (`components/live/live-activity-feed.tsx`) — every one of the 17 console
  pages before this was a Server Component rendering one fetched payload
  once, and the other 7 client components are forms or pure UI-state
  widgets with no data lifecycle of their own.
- **Real bug found in testing, not the implementation**: `redis-py`'s
  `get_message()` checks the socket exactly once per call — it does not
  loop internally past the pending subscribe-confirmation message to keep
  waiting for a *real* message within one timeout window (confirmed
  against its source). A test asserting on a single bare call failed
  reliably; the production generator was never affected, since its
  `while True` loop already retries on the next iteration regardless.
- **Verified against the real running server, not just the test suite**:
  `TestClient.stream()` hung indefinitely reading this endpoint in this
  environment — Starlette's `BaseHTTPMiddleware` (which both
  `RequestContextMiddleware` and `RateLimitMiddleware` are) is known to
  have real complications with long-lived streaming responses, so this was
  checked against the actual risk, not dismissed as a test-harness quirk:
  `python -m app` + `curl -N`, with a decision committed on a second
  connection mid-stream, delivered the live event correctly with the
  exact expected payload. The pytest suite tests the generator function
  directly instead (fast, reliable, exercises the real logic) rather than
  fighting `TestClient`'s streaming behavior on this specific stack.

---

## 6. Recurring design principle

The through-line in every review comment and commit message:

> **Prefer an honest gap to a plausible fabrication.**

Concretely: residuals are surfaced rather than distributed; rates ship with
their denominators; thin evidence is flagged *and* prevented from setting the
bar; "tamper-evident" is never called "tamper-proof"; drivers are labelled
"current, not historical" because attribution is not snapshotted; a searched
boundary is never labelled exact.

---

## 7. Current state

- **517 tests pass on a fresh seed, and the suite is now repeatable without
  one** — see resolved issues below (3 of the 517 are the real-data risk
  model's, and skip when that dataset hasn't been fetched locally).
- Lint clean (ruff + eslint), typecheck clean, production build clean.
- Both Docker images built and verified end-to-end: API (runs non-root,
  connects to Postgres, serves login, config guardrail fires inside the
  container) and, as of 2026-09-01, web (`docker build -f apps/web/Dockerfile
  .` from repo root; container reports healthy, `GET /` and `GET /login`
  both 200).
- CI (`.github/workflows/ci.yml`) runs on every push to `main` and every
  pull request — lint, format-check, full test suite, web build/typecheck,
  both Docker images, and a gitleaks secrets scan.
- Structured JSON logging with per-request correlation IDs, and Redis-backed
  rate limiting (on by default; the test suite explicitly opts out — see
  Phase 15 below), are both live.

### Known open issues

1. **Ledger `append` is not multi-writer safe** (documented in code).
2. **A full `GET /ledger/verify` genuinely must read the whole chain** —
   this is not a lingering gap, it's what the guarantee *means* (see
   Resolved below for what changed and what deliberately didn't).
3. **No equivalent of the `JWT_SECRET`/`BOOTSTRAP_ADMIN_PASSWORD` production
   guardrail exists for `DATABASE_URL`/`REDIS_URL`** — see
   `docs/operations/secrets.md`. Left open rather than guessed at, since
   "insecure" for a connection string needs a deliberate definition.
4. **No self-serve password-change flow.** Rotating the bootstrap admin
   password today means minting a replacement admin via `POST /auth/users`
   and retiring the original — see `docs/operations/secrets.md`.
5. **No live way to submit a vertical pack's domain attributes.**
   `POST /decisions/execute` and `POST /simulation/run` have no
   `attributes` field on their request schemas — every pack's rules
   (investments, travel, booking, it_ops) are real and correctly enforced
   against a decision that carries matching attributes, but the only thing
   that ever populates them today is `app/seed_domains.py` writing
   straight into the `investigation` JSONB blob. Found while adding
   it_ops; pre-existing for every pack, not something new to that one. See
   §5 Vertical Packs above for the full trace.
6. **No true live-traffic-split canary for ML models** — `app/ml/promote.py`
   (see Resolved below) gates promotion on held-out metrics, not on routing
   a percentage of real traffic to a candidate; that needs weighted routing
   across replicas, infrastructure this project doesn't have.

### Resolved (kept for history — both were live for a while, worth knowing why)

1. ~~Suite not repeatable without reseeding~~ — fixed 2026-09-01. Root cause:
   `test_recompute_records_a_snapshot_for_every_agent` and
   `test_recompute_is_stable_when_nothing_changed` call the real
   `POST /trust/recompute`, which commits one live snapshot per agent per
   call — real persistence against the shared dev DB, which is the point of
   those two tests. Nothing rolled those rows back, so they accumulated
   across every test run anyone ever did, and `assess_drift`'s 40-snapshot
   window eventually filled with enough flat "nothing changed" entries to
   crowd the seeded decline for `agt-expense-02` out of it —
   `test_declining_agent_is_flagged_as_drifting` then failed for reasons
   that had nothing to do with correctness. Fixed with a
   `_recompute_leaves_no_residue` fixture (`tests/test_trust_api.py`) that
   deletes exactly the rows those two tests add — same "prove it, then
   leave no trace" principle as
   `test_editing_a_stored_entry_breaks_verification` in
   `test_decision_pipeline.py`. Commit `c316b19`.
2. ~~Web Docker image never built~~ — fixed 2026-09-01, two real bugs found
   by actually building it for the first time:
   - `apps/web/Dockerfile` copied `/repo/apps/web/node_modules` from the
     deps stage, which `npm ci` never creates when there's only one npm
     workspace (everything hoists to the root `node_modules`) — that COPY
     failed unconditionally. Dropped it.
   - `package-lock.json` only had the `win32-x64-msvc` native-binary variant
     for `lightningcss`, `@tailwindcss/oxide`, and `unrs-resolver` (it was
     last regenerated on this Windows machine, and npm only records an
     installable entry for the platform that resolved it), so `npm ci`
     inside the Linux build stage had no `linux-x64-musl` binary and the
     Tailwind v4 build failed. Fixed by resolving a fresh lockfile inside
     `node:22-alpine` and splicing in only the missing platform-variant
     entries (dependency-closure walk, not a wholesale relock — that would
     have also silently bumped ~50 unrelated transitive packages). Diff is
     purely additive. Commit `80a3008`.

### Phase 15 — operational readiness (2026-09-01)

Feature build (Phases 0–13) was already complete; this closed the gap
between "works" and "operationally ready." Six streams, all shipped and
verified against the full suite:

1. **Structured logging + request correlation** — every log line is now one
   JSON shape (`app/core/logging.py`); `RequestContextMiddleware`
   (`app/core/middleware.py`) assigns/propagates an `X-Request-ID` and logs
   one line per request. Commit `4566ba4`.
2. **Rate limiting** — Redis-backed fixed window
   (`app/services/rate_limiter.py`), finally using the Redis that's been
   provisioned in both compose files since Phase 0 and never once imported
   by application code before this. Tighter budget on `POST /auth/login`,
   fails open on a Redis error. `/health` now checks Redis too. Found and
   fixed a real bug along the way: a naive `@lru_cache` Redis singleton
   broke under this repo's own test suite, which legitimately runs more
   than one independent `TestClient(app)` (each its own event loop) —
   `app/core/redis.py` now rebinds when the running loop changes instead of
   caching forever. Commit `4566ba4`.
3. **CI** — `.github/workflows/ci.yml`: api (postgres+redis service
   containers, ruff, pytest), web (lint, typecheck, build), docker (builds
   both Dockerfiles — a direct regression guard against the Phase 14 bug
   where the web image had never once been built), secrets-scan (gitleaks).
   Commit `2d5f363`.
4. **Backup/restore** — `infra/scripts/backup.sh`/`restore.sh` +
   `docs/operations/backup-restore.md`. Postgres only, deliberately — Redis
   is derived/short-lived state, ML artifacts are regenerable build output.
   Commit `2d5f363`.
5. **Secrets** — `docs/operations/secrets.md`: generation/rotation for each
   secret, what the `config.py` guardrail does and doesn't cover, gitleaks
   in CI as the enforcement half. Commit `2d5f363`.
6. **Pagination** — `limit`/`offset` on every list endpoint that grows with
   real usage (`/agents`, `/policies`, `/simulations`, `/policy/policies`,
   `/auth/users`, `/auth/api-keys`; `/decisions` already had `limit`, added
   `offset`), plus `X-Total-Count` response headers rather than a
   body-shape change. Real fix, not just a cap:
   `trust_service._load_decisions` now filters server-side by the same
   7-day anomaly window `compute_anomaly_penalty` already uses internally,
   instead of loading an agent's entire decision history to throw away
   everything past a week — provably wasted work, not a heuristic. Found
   `GET /simulations` scales 1:1 with decisions (not seed-scale small like
   the others), which broke `test_rebuild_covers_every_decision`'s old
   assumption of an unbounded response; fixed the test to read
   `SimulationRun` directly rather than loosen the cap. Deliberately left
   unbounded, see Known open issues: `ledger_service.load_chain` (needs
   whole-chain reads to verify hash links) and the `/trust/overview` N+1
   query pattern (needs one `AsyncSession` per task to parallelize safely).
   Commit `97ab9cd`.

### Phase 16 — scale & lifecycle (2026-09-03)

Three items were bundled under this name: ledger verification at scale,
parallelizing `/trust/overview`, and a model-retraining/canary strategy.
Full exploration of all three before writing anything changed the scope —
recorded here because the finding is itself worth keeping, not just the
code:

1. **`/trust/overview` parallelization — investigated, deliberately not
   built.** The actually expensive thing this issue conflated was fitting a
   fresh `IsolationForest` per agent (~340ms × N) — already fixed,
   separately, by making `include_ml_anomaly` opt-in and off by default
   (`trust_service.py`'s own docstring: "about six seconds of work whose
   result was never read"). What's left is 3 lightweight,
   already-window-filtered queries per agent. Parallelizing it would have
   been the first-ever use of concurrent `AsyncSession`s anywhere in this
   codebase (grepped `asyncio.gather`/`TaskGroup`/`create_task` across all
   of `apps/api/app`: zero hits) — real, untested complexity for marginal
   gain on a call this project's own docs already didn't consider urgent.
   No code changed; Known open issue #3 (parallelization) is retired as a
   TODO because the investigation found there wasn't a live one, not
   because a rewrite fixed it.
2. **Ledger — chunked full verification, plus a new, honestly-weaker fast
   path.** `ledger_service.load_chain` now fetches via a server-side cursor
   (`stream_scalars`/`yield_per`) instead of one query buffering the whole
   resultset in the driver at once — bounds *database-side* memory only;
   the returned list is still the full ordered chain, because a partial
   window genuinely cannot prove the part it can't see (§5 Ledger). New
   `GET /ledger/verify?sinceSeq=N` (`ledger_service.verify_since`) checks
   only what's new since a checkpoint plus that the checkpoint entry itself
   still matches its hash — `LedgerVerifyResponse.complete` says which kind
   of check ran. Explicitly tested in both directions, not just the
   reassuring one: `test_verify_since_catches_a_tampered_checkpoint_but_
   not_an_earlier_tamper` proves a full walk still catches a tamper
   anywhere in history, and the fast path from a later checkpoint does not
   — a real limit, not a bug, and asserted as such.
3. **ML retraining/canary — the real gap, now closed.** No versioning
   existed at all: `train.py`/`train_risk_model.py` overwrote the one live
   `*.joblib` set directly, no rollback, no comparison. Both scripts gained
   `--output-dir` (defaults unchanged — CI and the README's plain
   `python -m app.ml.train` are unaffected) and `--seed`, so a candidate can
   be built genuinely differently from live rather than reproducing it
   (training data is otherwise fully deterministic). New
   `app/ml/promote.py`: compares candidate `metrics.json` against live on
   every metric this project already reports, refuses to promote a
   regression past tolerance without `--force --reason`, then swaps
   candidate in with a timestamped backup (`rollback` reuses it). New
   `POST /trust/reload-models` (`RequireAdmin`) clears the `lru_cache`d
   loaders so a promotion takes effect on a running process without a
   restart — closes a loop that was previously fully manual (redeploy the
   whole image; `docker-compose.prod.yml` has no volume for artifacts, they
   ride along inside `COPY app ./app` as an accident of an unfiltered copy,
   not a designed mechanism).

   **Real bug caught by actually running this against the real live
   artifacts, not just reading the code**: the first `promote()`
   implementation did a wholesale directory swap. Promoting a candidate
   that only retrained the trust model (no `train_risk_model.py` run) it
   silently *deleted* the live `risk_model.joblib` — it was never in the
   candidate directory at all. Caught immediately during verification, not
   shipped: fixed to overlay onto a full backup of what was live instead of
   replacing the directory wholesale, with `metrics.json` getting the same
   per-key merge `train.py`/`train_risk_model.py` already do internally.
   Two regression tests lock this in
   (`test_promote_preserves_a_live_artifact_the_candidate_never_touched`,
   `test_promote_merges_metrics_json_rather_than_replacing_it`).

   No live traffic-split canary (routing a percentage of real requests to
   a candidate) — needs weighted routing across replicas, infrastructure
   this project doesn't have; comparison-gated promotion serves the same
   don't-ship-a-worse-model goal without it. See Known open issue #6.

---

## 8. Mentor feedback — the roadmap ahead

Five directions raised, mapped to status:

| # | Point | Status |
| --- | --- | --- |
| 1 | Rank N agents doing the same job (security/speed/efficiency) | ✅ **Phase 11** |
| 2 | Mechanism ranking — what changed that moved the score | ✅ **Phase 11** |
| 3 | Verticals: mutual funds, portfolio mgmt, travel (safety/privacy), booking | ✅ **Phase 13** |
| 4 | IT Ops: system analysis, log analysis, app/transaction scaling in banks | ✅ **added 2026-09-02** |
| 5 | Resource analysis / "how much to grow" — e.g. a bank scaling customer service | ✅ **Phase 12** |

**All five addressed.** #4 (IT Ops) turned out not to need a special
mechanism despite being flagged as the largest lift — the vertical-pack
mechanism from Phase 13 was already built generically enough to take a
non-financial domain (`CORE_FIELDS.amount_usd`'s own docstring already
said "absent for non-financial actions," before this pack existed to
prove it). See §5 Vertical Packs for the `it_ops` pack itself and the real
gap found while adding it (no live way to submit domain attributes through
the actual API yet, for any of the four packs — Known open issues #6).

---

## 9. Conventions for whoever picks this up

- **Read `apps/web/AGENTS.md` before touching frontend code.** Next.js 16 has
  breaking changes vs training data — e.g. `middleware.ts` is deprecated and
  renamed `proxy.ts`. Consult `node_modules/next/dist/docs/`.
- Engines are pure; services do I/O. Keep it that way.
- Comments explain **why**, especially non-obvious trade-offs. Match the
  existing density.
- Tests are named as behaviours (`test_an_unproven_agent_cannot_lead_the_cohort`)
  and carry a docstring saying why the behaviour matters.
- Commit messages are prose explaining the reasoning and any bug found, not a
  changelog.
- Standing instruction from the repo owner: **commit and push each completed
  phase to `main` without asking**.
