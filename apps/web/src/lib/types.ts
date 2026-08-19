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

/** Maps a 0–100 score onto its trust band. */
export function trustBand(score: number): TrustBand {
  if (score >= 90) return "trusted";
  if (score >= 75) return "healthy";
  if (score >= 60) return "watch";
  return "restricted";
}
