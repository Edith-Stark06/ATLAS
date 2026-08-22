# ATLAS — Technical Disclosure

**Adaptive Trust & Lifecycle Assurance System: Machine-Learned Governance for Autonomous Financial Agents**

Prepared as an invention disclosure for review by a registered patent agent.
This document describes what was built, why it is technically distinct from
prior art, and includes the quantitative evaluation evidence needed to argue
technical effect under Section 3(k) of the Indian Patents Act (and the
analogous "significantly more than an abstract idea" standard under US
post-*Alice* case law, if filed there instead or in addition).

**This is an engineering document, not a legal one.** Candidate claim
language appears in §7 as a starting point for counsel, not as a filed
claim. Inventor names, filing jurisdiction, and priority strategy are left
for the applicant and patent agent to complete.

---

## 1. Field of the Invention

Governance and access-control systems for autonomous software agents that
take real-world financial actions (payments, approvals, settlements) without
per-action human sign-off — specifically, a system that computes whether an
agent should be trusted to act *at the moment of the action*, using models
trained on the agent's own operational history, rather than a static,
hand-configured permission or scoring rule.

## 2. Background and the Technical Problem

Existing approaches to governing autonomous agents fall into two categories:

1. **Static access control** (RBAC/ABAC): an agent is granted a fixed
   permission set at deployment time. The permission does not change as the
   agent's behaviour changes, and cannot express "trusted for this action
   under these conditions, but not those."
2. **Rule-based / heuristic risk scoring**: a designer hand-assigns weights
   to a small number of signals (e.g. "policy compliance counts for 24%,
   risk exposure for 20%") and computes a score as their weighted sum. This
   is the approach ATLAS itself shipped with initially (`app/services/
   trust_engine.py`, `FACTOR_WEIGHTS` in `app/seed.py` — a fixed dict:
   `{"behavior": 0.22, "policy": 0.24, "risk": 0.20, "context": 0.14,
   "history": 0.20}`).

**The technical problem with (2)**, which this invention addresses directly:
a hand-set weighting cannot be verified against the actual relationship
between signals and outcomes, and — critically — cannot distinguish signals
that are genuinely diagnostic of near-term risk from signals that are only
weakly diagnostic. A designer who assigns comparable weight to five signals,
when in fact only two of them carry most of the real information, produces
a score that is *measurably* worse at ranking risk than one where the
weights are fit to labelled outcome data. This is not a hypothesis — §6
below reports a controlled comparison demonstrating the gap.

A second, related problem: static-threshold anomaly detection (e.g. "flag
if today's score is 5 points below the 7-day average") applies the same
threshold to every agent, in a feature space where three of five available
signals are structurally weak proxies for the thing actually being
detected. Distance/isolation-based anomaly detection is known to degrade as
irrelevant dimensions are added (the curse of dimensionality); a fixed
threshold over a fixed, undifferentiated feature set cannot correct for
this per agent.

## 3. Summary of the Invention

ATLAS replaces both the hand-set scoring formula and the static drift
threshold with models trained on labelled operational outcomes, integrated
into the same real-time, pre-execution governance pipeline:

```
Agent Request → Trust Engine → Policy Brain → Simulation Engine
             → Governance Decision → Explain AI → Governance Ledger → Execution
```

Three trained components, each replacing a specific heuristic, and coupled
to each other rather than developed independently:

| # | Component | Replaces | Technique |
|---|---|---|---|
| A | Trust scoring | Hand-set weighted mean | Logistic regression fit to labelled adverse-outcome data |
| B | Behavioural drift detection | Fixed threshold vs. population mean | Per-agent Isolation Forest, fit on that agent's own history, restricted to the features the trust model (A) itself identifies as informative |
| C | Outcome simulation | Fixed percentages, identical for every decision | Multi-class gradient-boosted classifier predicting approve/escalate/block probabilities from the specific decision's features |

Component B's coupling to Component A — using the trust model's own learned
`|coefficients|` to select which features the anomaly detector is fit on —
is a specific technical integration, not two independently-deployed models:
the system's own learned understanding of "what matters" is what determines
what the anomaly detector is allowed to look at. This is implemented in
`app/services/trust_service.py::evaluate_agent` (loads the trust model,
computes its prediction, then passes the same model into
`TrustModel.detect_anomaly`) and validated in the training pipeline
(`app/ml/train.py::evaluate_anomaly_detection`, `feature_weights` parameter).

Every score the system produces is accompanied by a per-factor attribution
(SHAP values on the linear model, exact rather than sampled — see §5.4) and
a plain-language, step-by-step explanation
(`app/services/trust_engine.py::evaluate`, the `explanation` list) —
explainability is a first-class output of the pipeline, not a separate
audit step applied after the fact.

## 4. Why the Learned Weighting Is Not Merely "The Same Idea, Automated"

A likely examiner objection: fitting weights to data is a well-known
statistical technique (logistic regression predates this filing by decades),
so is this just automating arithmetic a human already did? Two responses,
both grounded in the implementation:

1. **The claim is not "use regression."** It is the specific system
   architecture in which (a) the fitted model's score gates real-time
   execution of a financial action before it happens, (b) the same fitted
   model's feature importances are re-used to constrain a second,
   structurally different model (the per-agent anomaly detector) rather than
   being discarded after training, and (c) the fitted model's coefficients
   are exposed back through SHAP as the *content* of a mandatory
   human-readable explanation gating a governance decision. The technical
   effect is on the operation of the gating system — reduced false-positive
   rate on drift detection (§6.2), better-calibrated pre-execution risk
   ranking (§6.1) — not merely a data-science result sitting beside the
   system.
2. **The system degrades gracefully and deterministically**, and this
   degradation is itself part of the mechanism: `app/ml/models.py`'s loaders
   return `None` when no trained artifact is present, and
   `trust_engine.evaluate()` (`app/services/trust_engine.py`) falls back to
   the closed-form heuristic with no code branch difference visible to the
   caller. `app/seed.py::build_trust_history` further demonstrates a
   technical solution to a concrete engineering problem this design
   introduces — mid-flight replacement of a scoring methodology without
   discarding or corrupting historical continuity (§5.5).

## 5. Detailed Description

### 5.1 Trust Scoring Model (`app/ml/train.py::train_trust_model`)

- **Features**: five trust factors per agent (`behavior`, `policy`, `risk`,
  `context`, `history`), each 0–100.
- **Label**: whether the agent's *next* recorded decision was adverse
  (blocked or escalated) — a forward-looking label, deliberately not
  "was the current decision adverse," so the score predicts near-term risk
  rather than describing the past (`app/ml/dataset.py
  ::build_trust_training_frame`).
- **Model**: `sklearn.linear_model.LogisticRegression` over standardised
  features. Linear and interpretable by construction — the fitted
  coefficients *are* the learned factor weights, occupying the same
  conceptual role as the hand-set `FACTOR_WEIGHTS` dict it replaces, which
  keeps the explanation exact (§5.4) rather than approximated.
- **Score**: `100 × (1 − P(next decision adverse))`, computed at request
  time in `app/ml/models.py::TrustModel.predict`.
- **Training data**: synthetic (§5.6) — 320 simulated agents × 60 time
  steps, split by agent (not by row) into train/test, so no agent's own
  future leaks into its own past fold
  (`app/ml/dataset.py::train_test_split_by_agent`).

### 5.2 Per-Agent Anomaly Detection (`app/ml/models.py::TrustModel.detect_anomaly`)

- Fit fresh, per agent, per evaluation, on that agent's own stored trust
  history (`TrustSnapshot.factors`, JSONB) — not a population model.
- Restricted to the top-2 features by `|coefficient|` from the trust model
  (§5.1) rather than all five raw factors. This is feature *selection*, not
  weighting: `sklearn.ensemble.IsolationForest` selects a split feature
  uniformly at random at every tree node regardless of scale, so
  multiplying a noisy column by a constant has no effect — only removing it
  does (confirmed empirically; see the code comment and commit history in
  `app/ml/train.py::evaluate_anomaly_detection` documenting the
  scaling-had-no-effect finding that led to selection instead).
- `contamination` (the model's expected outlier fraction) is estimated from
  training-set statistics conditioned on "this agent has at least one
  historical drift event" — not from the evaluated agent's own ground
  truth, keeping the comparison in §6.2 non-leaky.
- Falls back to `None` ("not enough history yet") below six data points
  (`MIN_HISTORY_FOR_ANOMALY`) rather than fitting a meaningless model on two
  or three samples.

### 5.3 Simulation Outcome Model (`app/ml/train.py::train_simulation_model`)

- Multi-class classifier (`HistGradientBoostingClassifier`, with early
  stopping forced on regardless of dataset size — see §8, Implementation
  Notes) predicting `{approved, escalated, blocked}` probabilities from a
  specific decision's features: risk score, log-transformed amount, hour of
  day, policy pass rate, trust proxy, and the agent's authority level.
- Directly replaces literally-fixed percentages: the pre-ML system rendered
  the same three numbers (e.g. "18% / 64% / 18%") for every simulated
  decision regardless of its content — a static UI fixture, not a
  computation. The trained model computes a different distribution for
  every input (verified by `tests/test_trust_api.py
  ::test_simulate_responds_to_its_inputs`, which asserts a risky,
  off-hours, high-amount request scores materially different approval
  probability than a clean daytime one).
- Exposed as `POST /api/v1/trust/simulate` (`app/api/routes/trust.py`) — a
  stateless what-if endpoint, separate from historical `SimulationRun`
  records attached to real decisions.

### 5.4 Explainability (SHAP)

`app/ml/models.py::load_trust_model` constructs a `shap.LinearExplainer`
against the trust model. Because the model is linear, this attribution is
**exact**, not a sampled approximation (as SHAP requires for non-linear
models) — a specific, deliberate consequence of the model choice in §5.1.
Per-factor attribution is surfaced in the API response
(`TrustEvaluationRead.ml_attribution`) and rendered in the console as the
top contributing factors alongside every score
(`apps/web/src/app/(console)/trust-engine/page.tsx::ScoreBreakdown`).

### 5.5 Zero-Discontinuity Methodology Transition

A system that can switch its scoring methodology (heuristic → learned) at
runtime introduces a specific engineering problem: if historical records
were computed under the old methodology and the live score suddenly uses
the new one, every agent appears to "drift" the moment the model is
deployed — an artifact of the transition, not of agent behaviour. This was
observed directly during development (documented in commit history) and
solved in `app/seed.py::build_trust_history`: when a trained model is
present, the backfilled historical record is generated *under that model*
(interpolated factor vectors are scored by the same `TrustModel.predict`
used at runtime), so the full history is methodologically coherent with the
live score from the first evaluation, not just eventually after enough
`recompute` cycles accumulate new data.

### 5.6 Training Data Methodology

No real-world decision history exists to train on. `app/ml/dataset.py`
generates a synthetic dataset with disclosed, inspectable structure:

- Each simulated agent follows one of six behavioural archetypes (stable,
  degrading, recovering, volatile, onboarding) over 60 time steps.
- Two **partially correlated but distinct** latent quality axes
  ("operational" and "compliance") drive the five observed factors, each
  through a different blend ratio and a different *signal strength* — three
  of five factors are deliberately mostly idiosyncratic noise
  (`FACTOR_SIGNAL_STRENGTH`), so equal-weighting them (as the hand-set
  baseline does) provably dilutes real signal. This structure, not a
  cosmetic difference in the two weight sets, is what makes the
  baseline-vs-learned comparison in §6 a genuine test of whether weight
  discovery matters, rather than an artifact of arbitrary parameter choice.
- Decision outcomes are sampled from a noisy sigmoid over a **true**
  factor-weighting (`TRUE_OUTCOME_WEIGHTS`) that is deliberately different
  from the system's hand-set baseline weights — the model never sees this
  constant, only labelled outcomes, and has to recover the relationship
  from data alone.
- Drift events are injected as sustained level-shifts with recorded ground
  truth, which is what makes precision/recall evaluation of the anomaly
  detector (§6.2) possible at all.
- Train/test split is by agent, never by row (§5.1) — this is stated
  explicitly because it is the detail most commonly gotten wrong in a
  temporal-data evaluation, and getting it wrong would invalidate every
  number in §6.

### 5.7 Tamper-Evident Governance Record with Model and Rule Pinning

(`app/services/ledger.py`, `app/services/decision_service.py`)

The output of a trained model is only auditable if the *conditions* that
produced it are recoverable. A stored decision saying "blocked" is not
evidence: the model has since been retrained and the policy has since been
re-authored, so nothing in the database can reproduce the verdict.

Each committed decision therefore appends one record binding together, in a
single hash preimage:

- the inputs **as resolved** (defaults substituted, not the caller's nulls);
- the authenticated actor that committed the decision, distinguished by
  credential type (human operator versus machine credential);
- the identifier *and version string* of every governance rule evaluated,
  with its match result and effect;
- a SHA-256 fingerprint computed over the trained model artifacts
  themselves, rather than a recorded training timestamp;
- the predicted outcome distribution and the resulting decision; and
- the monetary exposure permitted and withheld, in fixed-point decimal.

The record's hash covers its sequence position, its predecessor's hash, its
type, its subject and its timestamp in addition to that payload, under a
canonical serialisation (sorted keys, no insignificant whitespace,
non-serialisable types rejected rather than coerced). Verification
recomputes the entire chain rather than consulting a stored validity flag.

The technical effect is specific: modifying any recorded field of any
historical decision — including reordering records or reassigning one to a
different decision — invalidates that record's hash and every subsequent
hash, and the discrepancy is localisable to the individual record and field.
Pinning the artifact fingerprint further distinguishes "this model decided
this" from "a model with this name decided this", which is the distinction
that matters once the model has been retrained.

This is deliberately characterised as tamper-*evident*. Tamper-*proofing*
requires anchoring the chain head outside the operator's control and is not
claimed here.

### 5.8 Verified Counterfactual Generation (`app/services/explanation_engine.py`)

A governance refusal that cannot be acted on is of limited operational value.
The system therefore computes, for a restricted action, the minimal change to
a single operator-controllable input that would produce a different verdict.

Two derivations, kept distinct because their epistemic status differs:

- **Rule-derived (exact).** For each matched ordered condition of a binding
  rule, the boundary value is computed arithmetically from the operator and
  threshold, stepped by the field's own granularity (integer fields by one,
  monetary fields by one cent).
- **Model-derived (searched).** Where the trained classifier rather than a
  rule determined the outcome, the boundary is located by scanning the
  feature's admissible range outward from its current value. Bisection is
  specifically *not* used: the gradient-boosted classifier of §5.3 is not
  monotonic in its inputs, and a binary search over a non-monotone response
  converges on a boundary that does not exist. Scanning outward in both
  directions also guarantees the *nearest* boundary is returned rather than
  the first encountered in scan order.

The step that distinguishes this from a per-rule sensitivity report: each
candidate is **re-evaluated against the complete active policy set** before
being offered, and retained only if the combined verdict actually changes.
A boundary is computed per rule, but the verdict is a function of all of
them — where two rules bind, satisfying one leaves the other in force, and
the arithmetically-correct boundary for the first is operationally useless.
The resulting outcome is reported as computed rather than assumed to be
approval; clearing a blocking rule frequently leaves a human-review
requirement in place.

Counterfactual search is restricted to a closed set of operator-controllable
fields. Fields describing the agent's governance state (lifecycle, capability)
are excluded by construction, so the system cannot suggest that an operator
alter the state being governed.

## 6. Technical Effect — Evaluation Results

Produced by `python -m app.ml.train`, written verbatim to
`apps/api/app/ml/artifacts/metrics.json`. Numbers below are from the run
dated in that file; re-running the training script regenerates them
deterministically (fixed seed, `DatasetConfig.seed = 20260820`).

### 6.1 Trust Scoring

| Metric | Hand-set weights (baseline) | Learned weights | Change |
|---|---|---|---|
| AUC (ranking near-term adverse-outcome risk) | 0.632 | 0.670 | **+6.1%** |

The fitted coefficients (`{"policy": -0.463, "risk": -0.241, "behavior":
-0.0003, "context": 0.0013, "history": -0.010}`) correctly identify `policy`
and `risk` as the dominant signals and the other three as near-irrelevant —
recovered *from labelled outcomes alone*, with no access to the synthetic
generator's ground-truth weighting. This is the single clearest piece of
evidence that the model is discovering real structure, not merely
reproducing its input.

### 6.2 Anomaly Detection

| Metric | Static threshold (baseline) | Per-agent Isolation Forest (learned) | Change |
|---|---|---|---|
| Precision | 0.179 | 0.308 | **+72%** |
| Recall | 0.500 | 0.368 | −26% |
| F1 | 0.263 | 0.335 | **+27%** |

Both precision and recall are reported rather than a single favourable
number — the honest result is a real, measured F1 improvement, not a
one-sided metric selected after the fact.

### 6.3 Simulation Outcome Prediction

| Metric | Fixed percentages (baseline) | Trained classifier (learned) | Change |
|---|---|---|---|
| Accuracy | 0.531 | 0.568 | +7% |
| Log-loss (lower is better) | 1.005 | 0.946 | **−6%** |

Log-loss is the primary claim here, not accuracy: the system exposes
*probabilities* to the operator ("64% recommend human review"), so
calibration quality is what matters, and log-loss is the metric that
measures it directly.

## 7. Candidate Claim Elements (for patent agent review — not final claims)

A computer-implemented method for governing execution of an action
requested by an autonomous software agent, comprising:

1. maintaining a plurality of trust factor scores for the agent;
2. computing, using a model trained on labelled historical decision
   outcomes for a population of agents, a trust score representing a
   calibrated probability that the agent's next action will be compliant;
3. determining, from the trained model's learned parameters, a subset of
   the trust factors most predictive of compliance;
4. fitting an anomaly-detection model exclusively on the determined subset
   of trust factors, using only the requesting agent's own historical
   values for those factors;
5. determining whether the agent's current factor values are anomalous
   relative to its own historical distribution, using the model of (4);
6. computing, from the trust score and a set of governance policies, a
   decision to approve, escalate for human review, or block the requested
   action, before the action is executed;
7. generating a human-readable explanation of the decision, including a
   per-factor attribution derived from the trained model of (2); and
8. recording the decision, the trust score, the anomaly determination, and
   the explanation in an append-only governance record prior to execution,
   the record further comprising a version identifier for each governance
   policy evaluated and a cryptographic digest computed over the trained
   model artifacts of (2); and
9. computing a cryptographic hash of the record of (8) over a canonical
   serialisation of the record together with the hash of the immediately
   preceding record, such that modification of any previously recorded
   decision is detectable by recomputation; and
10. binding, within the hashed record of (9), an identifier of the
    authenticated principal that authorised the action, distinguished by
    credential type, such that the attribution of a recorded decision is no
    more alterable than its outcome; and
11. determining, for an action restricted at (6), a minimal modification to a
    single one of a predetermined set of input values that would yield a
    different determination, by (a) computing the modification arithmetically
    from the threshold of a matched policy condition, or (b) where the
    determination arose from the trained model, locating it by evaluating the
    model across the admissible range of that input, and in either case
    re-evaluating the modified input against the complete set of governance
    policies and retaining the modification only where the resulting
    determination differs, the differing determination being reported as
    computed.

Dependent elements worth capturing separately: the fallback behaviour of
(2) when no trained model is available (deterministic heuristic
substitution, §4.2); the graceful transition mechanism of §5.5; the
multi-class outcome-probability prediction of §5.3 as a second, coupled
application of the same trained-model-gates-execution pattern; writing the
decision of (6) and the record of (8) within a single atomic transaction, so
no executed decision can lack an audit record; rejecting a repeated
external transaction reference rather than recording a second decision for
one event (§5.7); and restricting a machine credential to acting for a single
named agent, so that a compromised credential cannot commit decisions
attributed to another agent.

## 8. Implementation Notes for the Record

Two implementation bugs were found and fixed during development, both
worth preserving in the record as evidence of genuine engineering (not
retrofitted documentation):

- **Feature scaling vs. feature selection** (§5.2): an initial
  implementation attempted to weight the anomaly detector's input by
  multiplying columns by the trust model's coefficients. This measurably
  did nothing, because `IsolationForest` selects split features uniformly
  at random regardless of column scale. The fix — selecting a feature
  subset rather than reweighting — is what produced the result in §6.2, and
  the distinction is specifically why detect_anomaly's docstring calls out
  "selection, not rescaling."
- **Early stopping and dataset size**: `HistGradientBoostingClassifier`'s
  `early_stopping="auto"` only activates above 10,000 training rows. At the
  full training configuration (19,200 rows) this was invisible; a smaller
  configuration used in unit tests (4,000 rows) overfit badly enough to
  *worsen* log-loss relative to the naive baseline — caught by
  `tests/test_ml_train.py`, not by inspection. Forcing `early_stopping=True`
  unconditionally fixed it at both scales.

## 9. Prior Art Differentiation (for the patent agent's search)

Search terms likely to surface close prior art: "agent trust score,"
"behavioral drift access control," "autonomous agent governance gating,"
"AI agent risk scoring," fraud-detection and credit-scoring patents using
logistic regression or isolation forests generally. None reviewed to date
combine (a) pre-execution gating of an autonomous financial action, (b) a
trust model whose own learned feature importances constrain a second,
per-entity anomaly model, and (c) exact (non-sampled) SHAP explanation as a
mandatory output of the gating decision. Confirming this requires a formal
search by the patent agent; this section records the applicant's own
search terms and negative results as a starting point, not a clearance
opinion.

---

*Generated as part of ATLAS Phase 4 (ML-Enhanced Trust Engine). Source: see
`apps/api/app/ml/` and `apps/api/app/services/trust_service.py`. Evaluation
artifacts: `apps/api/app/ml/artifacts/metrics.json`.*
