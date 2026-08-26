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

This also creates the first admin account — `admin@atlas.local` /
`atlas-dev-admin` by default — but only when no users exist yet. `--reset`
reloads the governance dataset and deliberately leaves credentials alone.

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
| `/login` | Sign in | built in Next.js |
| `/console` | Control Center dashboard | `atlas-control-center` |
| `/console/agents` | AI Agent Registry | `ai-agent-registry` |
| `/console/policies` | Policy Governance + rule builder | `policy-governance` |
| `/console/decisions` | Decision Intelligence | `decision-intelligence-detail` |
| `/console/decisions/[id]` | Decision Investigation | `decision-investigation` |
| `/console/simulations` | Simulation Engine + scenario workspace | `simulation-engine-workspace` |
| `/console/explain` | Explain AI — drivers, rule evidence, counterfactuals | built in Next.js |
| `/console/benchmark` | Agent Benchmark — cohort ranking, gaps, change attribution | built in Next.js |
| `/console/analytics` | Governance Analytics — trends, latency, policy hot spots | built in Next.js |
| `/console/ledger` | Governance Ledger — chain integrity + audit records | built in Next.js |
| `/console/trust-engine` | Trust Engine | built in Next.js |
| `/console/status` | System health | — |

`/console/alerts` and `/console/settings` appear in the nav and route to
placeholders — they have no design yet and are marked "soon" in the sidebar.

The `executive-overview` export is ~90% identical to `atlas-control-center`
(which supersedes it as "Refined"), so it is not built as a separate route.

Every data-backed screen reads live from the API. If the backend is down the
route renders an explicit "Backend unavailable" panel rather than crashing.
The landing page is fully static and needs no backend at all.

## API

All responses are camelCase, so `apps/web/src/lib/types.ts` consumes them with
no mapping layer.

Everything except `/health` and `/auth/login` requires an
`Authorization: Bearer <credential>` header.

| Endpoint | Returns | Role |
| --- | --- | --- |
| `GET /api/v1/health` | Service + dependency health | — |
| `POST /api/v1/auth/login` | Exchange email + password for an access token | — |
| `GET /api/v1/auth/me` | Who the presented credential belongs to | any |
| `GET`·`POST /api/v1/auth/users` | List / create console accounts | admin |
| `GET`·`POST /api/v1/auth/api-keys` | List / mint service credentials | admin |
| `DELETE /api/v1/auth/api-keys/{id}` | Revoke a key (deactivates, never deletes) | admin |
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
| `GET /api/v1/explain/decisions/{id}` | Why a decision came out as it did, and what would change it |
| `GET /api/v1/analytics` | Aggregate trends over a rolling window (`days`) |
| `GET /api/v1/benchmark/cohorts` | Capabilities with agents in them — the rankable groups |
| `GET /api/v1/benchmark/cohorts/{capability}` | Rank every agent doing that job, with gaps to the leader |
| `GET /api/v1/benchmark/agents/{id}/changes` | Decompose an agent's score change by factor |

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

## Authentication & Roles

Everything except `/health` and `/auth/login` requires credentials. Two kinds
resolve to the same internal `Actor`, so a human operator and a service key
are treated identically by every permission check and every audit record —
the distinction is preserved *in* the actor, not scattered through call sites.

| Credential | For | Hashing |
| --- | --- | --- |
| Email + password → JWT | Console operators | **Argon2id** (slow, memory-hard) |
| `atlas_sk_…` API key | Agents and services | **SHA-256** (fast) |

The different hashing is deliberate. A password is low-entropy and
human-chosen, so a stolen table is only as safe as the cost of guessing each
candidate. An API key is 256 bits of `secrets` randomness — brute force is
already impossible, and a slow hash would add latency to every request an
agent makes without buying anything.

### Roles

| Role | Can |
| --- | --- |
| `viewer` | Read governance data; run what-if simulations |
| `operator` | …plus commit decisions, recompute trust, rebuild simulations |
| `admin` | …plus author policy versions and manage credentials |

Deliberately coarse. Fine-grained permissions invite a matrix nobody can
reason about, and the question this system must answer at review time is
"who could have committed this decision?" — which needs an answer short
enough to fit in a sentence.

- **The role is re-read per request**, never trusted from the token claim. A
  token minted before a demotion must not keep working at the old level.
- **Agent-bound keys.** A key may be pinned to one agent; it then cannot
  commit decisions in any other agent's name, so a compromised credential is
  limited to that agent's blast radius.
- **Keys are revoked, not deleted.** Their prefix appears as the actor behind
  past decisions, and erasing the row would leave audit records naming a
  credential nobody can identify.
- **Login answers identically** for an unknown account and a wrong password,
  and hashes either way, so the form is not an account-enumeration oracle.
- **Every decision records its actor** as `user:…` or `api_key:…`, inside the
  ledger hash. "The system approved it" is not an answer anyone can act on.

### In the console

The token is held in an **httpOnly** cookie, so page scripts cannot read it
and an XSS bug cannot exfiltrate a working credential. Client components
therefore cannot call the API directly; they go through the app's own
`/api/atlas/…` route, which attaches the token server-side. That is the trade:
one extra hop for a token JavaScript never touches.

`src/proxy.ts` (Next 16's renamed `middleware`) redirects unauthenticated
navigation to `/login`. It is **not** the security boundary — the presence of
a cookie proves nothing. Every request still carries the token to the API,
which validates it and enforces the role.

The first admin is created by `python -m app.seed`, and only when no users
exist at all. Once any account exists an operator has taken ownership, and
silently re-creating a known default admin underneath them would be a
backdoor.

---

## Deployment

```bash
cp .env.example .env
# set JWT_SECRET (openssl rand -hex 32) and BOOTSTRAP_ADMIN_PASSWORD
docker compose -f infra/docker-compose.prod.yml --env-file .env up --build
```

- **The API refuses to start** outside `development` while `JWT_SECRET` or
  `BOOTSTRAP_ADMIN_PASSWORD` is still the documented default, or the secret is
  under 32 characters. A misconfigured deployment that boots and looks healthy
  is discovered by an attacker; one that refuses to start is discovered by
  whoever ran the deploy.
- **Migrations run as a one-shot service**, not on API startup: with more than
  one replica, startup migrations race each other. The API waits for it to
  complete successfully.
- **Postgres publishes no host port.** Only the API needs it.
- **The API needs no browser-reachable URL either.** Browser traffic goes
  through the web server's proxy route, so the web container reaches the API
  at `http://api:8000` over the internal network.
- **Both images run as non-root** and carry a healthcheck. The API's probes
  `/api/v1/health`, so it is only "healthy" once Postgres is actually
  reachable — not merely once the process is listening.

## Explain AI

Three of the four things an explanation needs already existed: the trust
model's SHAP attribution, the policy engine's per-condition results, and the
pipeline's prose. `GET /explain/decisions/{id}` adds the fourth, which is what
makes an explanation actionable rather than merely descriptive:

> Blocked. Risk score 95 → at most 89 changes this to **escalated**.

- **Reconstructed from pinned evidence, not current state.** The rule
  *versions* and model fingerprint come from the ledger entry. Re-evaluating a
  six-month-old decision against today's policy set would produce a coherent,
  confident explanation of a decision the system never made.
- **Policy boundaries are exact; model boundaries are searched.** A rule is
  `risk_score > 90`, so the value that stops it matching is arithmetic. The
  classifier has no such structure, so its boundary is found by scanning the
  feature's real range — *not* by bisection, because gradient boosting is not
  monotonic and a binary search over a non-monotone response returns a
  plausible-looking boundary that is simply wrong. The two are labelled
  differently in the response (`exact: true|false`) rather than blurred.
- **Every suggestion is verified against the whole rule set.** A boundary is
  computed per rule, but the verdict comes from all of them. With two rules
  binding, "amount at most $2,000" can be exactly right about its own rule and
  useless as advice, because the sanctions rule still blocks. Each candidate
  is replayed and kept only if the combined outcome actually changes.
- **The new outcome is reported, not assumed.** Clearing a block often leaves
  a review requirement behind, so `changesTo` is frequently `escalated` rather
  than `approved`. Saying "this would have been approved" when it would not is
  the failure mode this avoids.
- **Suggestions stay inside what an operator can act on.** Trust, risk and
  amount are searchable; lifecycle state and capability are not. Telling
  someone to change an agent's governance state is not advice.
- **Drivers are labelled as current.** Per-factor SHAP attribution is not
  snapshotted, so the drivers describe the agent's trust *today*. That is
  flagged in the response and in the UI rather than passed off as the
  attribution at decision time.

## Governance Analytics

`GET /analytics?days=N` aggregates recorded activity over a rolling window.
Computed per request rather than from a maintained rollup: a governance
dashboard whose numbers can drift from the decisions they describe is worse
than no dashboard.

Two choices run through the whole module, because aggregate views are where
quiet lies live:

- **Percentiles, not means.** ATLAS sits in the critical path of an action
  about to happen, so what matters is what the slowest requests cost. On the
  current seed the mean is 109ms and p99 is 1913ms — reporting the average
  alone would hide an 8× tail. Percentiles are **nearest-rank**, so every
  figure is a request that actually happened; an interpolated p99 nobody ever
  measured is a worse answer for a latency budget than a real one.
- **Rates carry their denominator.** "8% violation rate" over 12 decisions is
  noise; over 12,000 it is a finding. Every rate travels with its sample size,
  in the API and on screen, so the two cannot be confused.

Other deliberate details:

- **Quiet days are rendered, not skipped.** A chart that drops silent days
  compresses the axis and makes a two-week lull look like continuous traffic.
- **Empty buckets are still reported.** "No agents are restricted" must not
  look identical to "that band does not exist".
- **A rate over nothing is 0%, not 100%.** `0/0` is a real state for a fresh
  estate, and rendering it as full compliance — or full violation — is worse
  than rendering nothing.
- **Dead rules are flagged, but only once tested.** A policy evaluated many
  times that has never matched is mis-scoped or redundant, which is
  actionable. A policy added yesterday has not had a chance to fire, so it is
  not labelled until it has been evaluated enough times to mean something.
- **Actions without an amount are excluded from exposure.** A card freeze is
  a governed action carrying no money; treating its absent amount as zero
  would drag the totals down.
- **The window is applied in SQL.** Pulling every decision ever recorded to
  count last week's works fine on seed data and falls over on a real estate.

## Agent Benchmark

Every earlier phase scores an agent in isolation — is *this* action safe.
This answers the question an operator actually asks: given ten agents doing
the same job, which should get more of the work, and what would the others
have to change to catch up.

`GET /benchmark/cohorts/{capability}` ranks a cohort on five criteria with
published weights:

| Criterion | Weight | Measures |
| --- | --- | --- |
| Security | 30% | Rate of actions the rules *blocked* — the agent proposed something it was not permitted to do |
| Compliance | 25% | Share of individual policy checks passed |
| Efficiency | 20% | Share of work completed without a human; escalations are the running cost of an estate |
| Reliability | 15% | Stability of the trust score — an agent swinging 40–90 averages the same as one steady at 65 |
| Speed | 10% | p95 latency against a fixed 50–2000ms budget |

The design guards against the ways a ranking quietly becomes wrong:

- **Only comparable things are compared.** Ranking across capabilities raises
  rather than returning a confident, meaningless ordering.
- **Scores are absolute, not normalised to the cohort.** Normalising makes the
  best member 100 and the worst 0 *by construction*, so a uniformly excellent
  estate would appear to contain a failing agent.
- **Security ignores escalations.** An escalation is the system working;
  penalising it would reward an agent for being merely timid.
- **An unexercised agent scores 0 on compliance, not 100.** No checks recorded
  is no evidence, not a clean record.
- **An unproven agent cannot be the benchmark.** The leader is what every
  other agent's gap is measured against, so one lucky decision must not set
  the bar. Thin-evidence agents sort below established ones with their real
  score still shown — sorted down, not doctored.
- **Gaps rank by what would move the composite**, not by raw point
  difference: a 30-point speed gap (weight 0.10) matters less than a 12-point
  security gap (weight 0.30).

### Mechanism ranking — what changed

`GET /benchmark/agents/{id}/changes` decomposes a score movement into the
factors that caused it. The base score is a weighted sum, so each factor's
share is arithmetic rather than estimated:

```
contribution = w_after·s_after − w_before·s_before
             = w_before·(s_after − s_before)   ← the factor moved
             + s_after·(w_after − w_before)    ← its weight was re-tuned
```

Those are separated because "policy compliance improved" and "policy
compliance now counts for more" are different events.

**The parts must sum to the whole.** Anything the decomposition cannot
account for is reported as a `residual` rather than spread across the
factors — an attribution that silently absorbs its own error is not an
attribution. In practice the residual is often large, and that is the useful
part: the trust score comes from a trained model, not the weighted sum this
decomposition assumes, so a big residual means *the model* judged the agent
differently for reasons its input factors do not capture.

The seeded `Customer Servicing` cohort (`app/seed_cohort.py`) is ten agents
tuned to lose ground on *different* criteria — fast-but-careless,
slow-but-impeccable, escalates-everything, unstable, brand-new — so the
weighting is visible doing work in the ordering rather than hidden by it.

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
| 8 | Auth, roles, actor attribution, containerised deployment | ✅ |
| 9 | Explain AI — drivers, rule evidence, verified counterfactuals | ✅ |
| 10 | Governance Analytics — trends, latency percentiles, policy hot spots | ✅ |
| 11 | Agent Benchmark — cohort ranking and score-change attribution | ✅ |
