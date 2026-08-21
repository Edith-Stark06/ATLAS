/**
 * Core ATLAS domain types.
 *
 * Phase 1 renders these from mock data; Phase 2 replaces the mock source with
 * the FastAPI backend while keeping these shapes as the contract.
 */

/** Lifecycle states an agent moves through after onboarding. */
export type LifecycleState =
  | "onboarding"
  | "healthy"
  | "anomaly"
  | "review"
  | "recovery"
  | "trusted";

/** Coarse band derived from a numeric trust score. */
export type TrustBand = "trusted" | "healthy" | "watch" | "restricted";

/** What the governance pipeline decided about a requested action. */
export type DecisionOutcome = "approved" | "escalated" | "blocked";

export type Severity = "low" | "medium" | "high" | "critical";

export interface TrustFactor {
  key: string;
  label: string;
  /** 0–100 */
  score: number;
  /** Relative contribution to the composite score, 0–1. */
  weight: number;
}

export interface Agent {
  id: string;
  name: string;
  /** Business capability, e.g. "Travel Booking". */
  capability: string;
  owner: string;
  lifecycle: LifecycleState;
  /** 0–100 */
  trustScore: number;
  /** Change over the last 24h, in points. */
  trustDelta: number;
  decisionsToday: number;
  /** ISO-8601 */
  lastActiveAt: string;
  factors: TrustFactor[];
  /** Underlying model powering the agent. */
  model: string;
  /** Autonomy tier 1–4; higher grants broader unattended authority. */
  authorityLevel: 1 | 2 | 3 | 4;
  /** ISO-8601 date of the last model audit. */
  lastAuditAt: string;
  /** Short summary of the most recent decision. */
  lastDecision: string;
}

export interface PolicyCheck {
  policyId: string;
  policyName: string;
  passed: boolean;
  detail?: string;
}

export interface Decision {
  id: string;
  agentId: string;
  agentName: string;
  /** Human-readable action, e.g. "Book flight LHR→JFK". */
  action: string;
  amountUsd: number | null;
  outcome: DecisionOutcome;
  /** Agent trust at decision time, 0–100 */
  trustScore: number;
  /** 0–100, higher is riskier */
  riskScore: number;
  policyChecks: PolicyCheck[];
  /** ISO-8601 */
  decidedAt: string;
  latencyMs: number;
  /** Plain-language rationale from Explain AI. */
  rationale: string;
  /** Present for decisions that were escalated or blocked. */
  investigation?: DecisionInvestigation;
}

export interface Policy {
  id: string;
  name: string;
  version: string;
  /** Which agents/capabilities it applies to. */
  scope: string;
  enabled: boolean;
  severity: Severity;
  /** ISO-8601 */
  updatedAt: string;
  evaluations24h: number;
  violations24h: number;
}

// --- Policy Brain -----------------------------------------------------------

export type RuleOperator = "lt" | "lte" | "gt" | "gte" | "eq" | "neq" | "in" | "not_in";
export type RuleCombinator = "all" | "any";
export type RuleEffect = "allow" | "require_human_review" | "block";

export interface RuleCondition {
  field: string;
  operator: RuleOperator;
  value: number | string | (number | string)[];
}

export interface PolicyRule {
  conditions: RuleCondition[];
  combinator: RuleCombinator;
  effect: RuleEffect;
  /** Capabilities governed; empty means every agent. */
  applies_to: string[];
}

export interface RuleFieldSpec {
  key: string;
  label: string;
  /** Python type name — "int", "float", "str". */
  kind: string;
  description: string;
}

/** Everything needed to compose a valid rule, served by the API so the
 * authoring UI cannot drift from what the engine accepts. */
export interface RuleVocabulary {
  fields: RuleFieldSpec[];
  operators: RuleOperator[];
  combinators: RuleCombinator[];
  effects: RuleEffect[];
  capabilities: string[];
}

export interface PolicyVersion {
  id: number;
  policyId: string;
  version: string;
  rule: PolicyRule;
  note: string;
  createdBy: string;
  createdAt: string;
}

export interface PolicyDetail extends Policy {
  /** Null when the policy has no active version yet. */
  rule: PolicyRule | null;
  /** Human-readable rendering of the active rule. */
  summary: string[];
  versions: PolicyVersion[];
}

export interface ConditionResult {
  description: string;
  matched: boolean;
  /** True when the condition could not be evaluated at all (missing value,
   * type mismatch) — distinct from evaluating cleanly to false. */
  skipped: boolean;
}

export interface PolicyEvaluation {
  policyId: string;
  policyName: string;
  version: string;
  matched: boolean;
  inScope: boolean;
  effect: RuleEffect | null;
  conditions: ConditionResult[];
}

export interface EvaluateRequest {
  trustScore: number;
  riskScore: number;
  amountUsd: number | null;
  authorityLevel: number;
  agentLifecycle: string;
  capability: string;
  hourUtc: number;
}

export interface EvaluateResponse {
  effect: RuleEffect;
  outcome: DecisionOutcome;
  explanation: string[];
  evaluations: PolicyEvaluation[];
  /** Policies whose stored rule could not be parsed. */
  invalid: string[];
}

export interface SimulatedDecision {
  decisionId: string;
  agentName: string;
  action: string;
  recordedOutcome: DecisionOutcome;
  simulatedOutcome: DecisionOutcome;
  matched: boolean;
  changed: boolean;
}

export interface SimulateRuleResponse {
  evaluated: number;
  matched: number;
  wouldBlock: number;
  wouldEscalate: number;
  wouldAllow: number;
  changed: SimulatedDecision[];
  sample: SimulatedDecision[];
}

/** Per-dimension risk breakdown, each 0–100. */
export interface RiskVector {
  financial: number;
  fraud: number;
  operational: number;
  regulatory: number;
}

export interface CriticalFactor {
  key: string;
  title: string;
  detail: string;
  severity: Severity;
}

/** Everything the investigation view needs beyond the decision record itself. */
export interface DecisionInvestigation {
  summary: string;
  criticalFactors: CriticalFactor[];
  actionRequired: string;
  /** Trust score before this decision's re-evaluation. */
  trustBefore: number;
  /** Model certainty, 0–100. */
  confidence: number;
  riskVector: RiskVector;
  trace: PipelineStage[];
  merchant?: string;
  /** Local wall-clock time the request originated, e.g. "03:14 EST". */
  requestedAtLocal?: string;
}

export interface SimulationOutcome {
  label: string;
  /** 0–1 */
  probability: number;
  financialImpactUsd: number;
  /** 0–100, higher is riskier */
  riskScore: number;
  compliant: boolean;
  /** Qualitative read-outs shown on the scenario cards. */
  customerExperience?: "High" | "Good" | "Poor";
  complianceRisk?: "Safe" | "Medium" | "High";
  recommended?: boolean;
}

export interface SimulationRun {
  id: string;
  decisionId: string;
  scenario: string;
  outcomes: SimulationOutcome[];
  recommendation: DecisionOutcome;
  /** ISO-8601 */
  ranAt: string;
  durationMs: number;
  agentName: string;
  amountUsd: number | null;
  trustScore: number;
  /** Model certainty, 0–100. */
  confidence: number;
  /** Key/value rows describing the incoming request. */
  request: { label: string; value: string }[];
}

// --- Pre-execution simulation (what-if, never persisted) ---------------------

export interface SimulateActionRequest {
  action: string;
  agentId?: string | null;
  amountUsd?: number | null;
  /** 0–100, higher is riskier */
  riskScore: number;
  /** Overrides the agent's stored score — this is what makes "what if trust
   * dropped to 40?" answerable. */
  trustScore?: number | null;
  hourUtc?: number | null;
  /** 0–1 */
  policyPassRate?: number;
}

export interface PredictedOutcome {
  outcome: DecisionOutcome;
  label: string;
  /** 0–1 */
  probability: number;
  financialImpactUsd: number;
  /** Residual risk if this path is taken, 0–100. */
  riskScore: number;
  /** Whether the active rules would permit this path. */
  compliant: boolean;
  recommended: boolean;
}

export interface PolicyTraceEntry {
  policyId: string;
  policyName: string;
  version: string;
  matched: boolean;
  inScope: boolean;
  effect: RuleEffect | null;
}

export interface SimulateActionResponse {
  recommendation: DecisionOutcome;
  /** Confidence in the recommended path, 0–100. */
  confidence: number;
  outcomes: PredictedOutcome[];
  /** Money that moves if the recommendation is followed. Deterministic —
   * nothing moves once the recommendation is to block or escalate. */
  expectedExposureUsd: number;
  withheldUsd: number;
  /** What an unpoliced system would expose on average. The gap against
   * expectedExposureUsd is what the governance layer is buying. */
  unconstrainedExposureUsd: number;
  /** 0–1 */
  adverseProbability: number;
  /** True when the rules, not the model, determined the recommendation. */
  policyForced: boolean;
  policyEffect: RuleEffect;
  policyTrace: PolicyTraceEntry[];
  agentName: string;
  trustScore: number;
  /** False when no trained classifier is loaded — probabilities are then an
   * even split, which reads as "no signal" rather than a confident guess. */
  modelBacked: boolean;
  durationMs: number;
  explanation: string[];
}

// --- Decision pipeline & governance ledger -----------------------------------

export interface ExecuteDecisionRequest {
  agentId: string;
  action: string;
  amountUsd?: number | null;
  /** 0–100, higher is riskier */
  riskScore: number;
  hourUtc?: number | null;
  /** Reference from the originating system. Generated when absent. */
  decisionId?: string | null;
}

export interface ExecuteDecisionResponse {
  decisionId: string;
  outcome: DecisionOutcome;
  /** True only when the action is cleared to run. Branch on this rather than
   * string-matching the outcome. */
  executed: boolean;
  agentName: string;
  trustScore: number;
  confidence: number;
  rationale: string;
  latencyMs: number;
  expectedExposureUsd: number;
  withheldUsd: number;
  ledgerSeq: number;
  ledgerHash: string;
}

export type LedgerKind =
  | "decision_recorded"
  | "policy_activated"
  | "trust_recomputed";

export interface LedgerEntry {
  seq: number;
  entryHash: string;
  prevHash: string;
  kind: LedgerKind | string;
  subjectId: string;
  /** The pinned evidence, hashed verbatim — this is what an auditor
   * recomputes against. Shape varies by kind. */
  payload: Record<string, unknown>;
  /** ISO-8601 */
  recordedAt: string;
}

export interface ChainBreak {
  seq: number;
  reason: string;
  expected: string;
  found: string;
}

export interface LedgerVerification {
  valid: boolean;
  entriesChecked: number;
  breaks: ChainBreak[];
  headHash: string | null;
}

export interface LedgerStats {
  entries: number;
  headHash: string | null;
  headSeq: number | null;
  /** ISO-8601 */
  firstRecordedAt: string | null;
  lastRecordedAt: string | null;
  countsByKind: Record<string, number>;
  /** SHA-256 of the trained artifacts on disk. A decision whose pinned
   * fingerprint differs was made by a different model. */
  modelFingerprint: string | null;
}

export type PipelineStageStatus = "done" | "active" | "pending" | "failed";

export interface PipelineStage {
  key: string;
  label: string;
  status: PipelineStageStatus;
  detail?: string;
}

export interface ActivityItem {
  id: string;
  message: string;
  /** ISO-8601 */
  at: string;
  tone: "info" | "success" | "warning" | "danger";
}

export interface DashboardMetric {
  key: string;
  label: string;
  value: string;
  tone: "primary" | "secondary" | "tertiary" | "error";
  icon: string;
}

export interface CompositeTrust {
  score: number;
  /** Null until the Trust Engine produces real forecasts (Phase 3). */
  predicted: number | null;
  factors: TrustFactor[];
  /** Trust recorded against recent decisions, oldest → newest. */
  trend: number[];
}

export interface LivePipeline {
  transactionId: string;
  stages: PipelineStage[];
}

export interface DashboardData {
  metrics: DashboardMetric[];
  compositeTrust: CompositeTrust;
  livePipeline: LivePipeline;
  activity: ActivityItem[];
}

/** How far an agent has moved against its own historical baseline. */
export interface Drift {
  detected: boolean;
  /** Current score minus baseline, in points. Negative means declining. */
  delta: number;
  baseline: number | null;
  samples: number;
}

export interface TrustSnapshot {
  score: number;
  baseScore: number;
  anomalyPenalty: number;
  reason: string;
  capturedAt: string;
}

/** Isolation Forest result for one agent's own accumulated history. */
export interface MLAnomaly {
  detected: boolean;
  /** decision_function output — more negative is more anomalous. Not a
   * fixed 0-100 scale like Drift.delta. */
  score: number;
}

export type ScoreSource = "ml" | "heuristic";

export interface TrustEvaluation {
  agentId: string;
  agentName: string;
  score: number;
  /** Weighted factor mean, before penalties. */
  baseScore: number;
  anomalyPenalty: number;
  lifecycle: LifecycleState;
  factors: TrustFactor[];
  drift: Drift;
  /** Null when there is too little history to project honestly. */
  forecast: number | null;
  /** Step-by-step account of how the score was reached. */
  explanation: string[];
  history: TrustSnapshot[];
  /** "ml" when a trained model produced `score`, "heuristic" otherwise. */
  scoreSource: ScoreSource;
  /** Per-factor SHAP contribution to `score`, in score units. Null when
   * scoreSource is "heuristic". */
  mlAttribution: Record<string, number> | null;
  /** Null when no trained model is loaded, or too little history exists. */
  mlAnomaly: MLAnomaly | null;
}

export interface SimulationPredictRequest {
  trustScore: number;
  riskScore: number;
  amountUsd: number;
  policyPassRate: number;
  authorityLevel: number;
  hour: number;
}

export interface PredictedOutcome {
  outcome: DecisionOutcome;
  probability: number;
}

export interface SimulationPredictResponse {
  outcomes: PredictedOutcome[];
  recommendation: DecisionOutcome;
}

export interface ModelInfo {
  available: boolean;
  trainedAt: string | null;
  metrics: Record<string, unknown> | null;
}

export interface TrustBandCount {
  band: string;
  label: string;
  count: number;
}

export interface TrustOverview {
  averageScore: number;
  agentsEvaluated: number;
  drifting: number;
  bands: TrustBandCount[];
  /** Ordered by drift, worst first. */
  watchlist: TrustEvaluation[];
}

export interface RecomputeResult {
  agentId: string;
  agentName: string;
  previousScore: number;
  score: number;
  lifecycle: LifecycleState;
  driftDetected: boolean;
}

export interface RecomputeResponse {
  evaluated: number;
  results: RecomputeResult[];
}

/** Maps a 0–100 score onto its trust band. */
export function trustBand(score: number): TrustBand {
  if (score >= 90) return "trusted";
  if (score >= 75) return "healthy";
  if (score >= 60) return "watch";
  return "restricted";
}
