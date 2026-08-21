import type {
  ActivityItem,
  Agent,
  DashboardData,
  Decision,
  EvaluateRequest,
  EvaluateResponse,
  ModelInfo,
  Policy,
  PolicyDetail,
  PolicyRule,
  PolicyVersion,
  RuleVocabulary,
  SimulateActionRequest,
  SimulateActionResponse,
  SimulateRuleResponse,
  RecomputeResponse,
  SimulationPredictRequest,
  SimulationPredictResponse,
  SimulationRun,
  TrustEvaluation,
  TrustOverview,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const REQUEST_TIMEOUT_MS = 5000;

export type DependencyStatus = "up" | "down";

export interface DependencyHealth {
  name: string;
  status: DependencyStatus;
  detail?: string | null;
}

export interface HealthResponse {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  environment: string;
  dependencies: DependencyHealth[];
}

/** Health as seen from the browser/server — adds the "API unreachable" case. */
export type HealthProbe =
  | { reachable: true; data: HealthResponse }
  | { reachable: false; error: string };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Cannot reach ATLAS API at ${API_BASE_URL} — ${message}`);
  }

  if (!res.ok) {
    throw new ApiError(`API responded ${res.status} for ${path}`, res.status);
  }

  return (await res.json()) as T;
}

/**
 * Wraps a fetch so a page can render a useful error state instead of a crash
 * when the backend is down — the common case during local development.
 */
export type Result<T> = { ok: true; data: T } | { ok: false; error: string };

export async function tryFetch<T>(fn: () => Promise<T>): Promise<Result<T>> {
  try {
    return { ok: true, data: await fn() };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function fetchHealth(): Promise<HealthProbe> {
  try {
    return { reachable: true, data: await apiGet<HealthResponse>("/health") };
  } catch (err) {
    return { reachable: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export const fetchDashboard = () => apiGet<DashboardData>("/dashboard");
export const fetchAgents = () => apiGet<Agent[]>("/agents");
export const fetchAgent = (id: string) => apiGet<Agent>(`/agents/${id}`);
export const fetchDecisions = () => apiGet<Decision[]>("/decisions");
export const fetchDecision = (id: string) =>
  apiGet<Decision>(`/decisions/${encodeURIComponent(id)}`);
export const fetchPolicies = () => apiGet<Policy[]>("/policies");
export const fetchSimulations = () => apiGet<SimulationRun[]>("/simulations");
export const fetchActivity = () => apiGet<ActivityItem[]>("/activity");
export const fetchTrustOverview = () => apiGet<TrustOverview>("/trust/overview");
export const fetchAgentTrust = (id: string) =>
  apiGet<TrustEvaluation>(`/trust/agents/${encodeURIComponent(id)}`);

/** Triggers a fresh evaluation of every agent and records new snapshots. */
export async function recomputeTrust(): Promise<RecomputeResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/trust/recompute`, {
    method: "POST",
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS * 4),
  });
  if (!res.ok) {
    throw new ApiError(`Recompute failed with ${res.status}`, res.status);
  }
  return (await res.json()) as RecomputeResponse;
}

export const fetchModelInfo = () => apiGet<ModelInfo>("/trust/model-info");

/** Scores a hypothetical decision with the trained outcome classifier — no
 * persistence, distinct from the historical SimulationRun records. */
export async function simulatePredict(
  request: SimulationPredictRequest,
): Promise<SimulationPredictResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/trust/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new ApiError(`Simulate failed with ${res.status}`, res.status);
  }
  return (await res.json()) as SimulationPredictResponse;
}

// --- Policy Brain -----------------------------------------------------------

export const fetchRuleVocabulary = () => apiGet<RuleVocabulary>("/policy/vocabulary");
export const fetchPolicyDetails = () => apiGet<PolicyDetail[]>("/policy/policies");
export const fetchPolicyDetail = (id: string) =>
  apiGet<PolicyDetail>(`/policy/policies/${encodeURIComponent(id)}`);

async function apiPost<T>(path: string, body: unknown, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
      body: JSON.stringify(body),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Cannot reach ATLAS API at ${API_BASE_URL} — ${message}`);
  }

  if (!res.ok) {
    // 422 carries the engine's own validation message, which is far more
    // useful to an author than a generic status line.
    let detail = `API responded ${res.status} for ${path}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body — keep the status line.
    }
    throw new ApiError(detail, res.status);
  }

  return (await res.json()) as T;
}

/** Runs the full active policy set against a hypothetical decision. */
export const evaluatePolicies = (request: EvaluateRequest) =>
  apiPost<EvaluateResponse>("/policy/evaluate", request);

/** Replays a candidate rule over stored decisions before it is deployed. */
export const simulatePolicyRule = (rule: PolicyRule) =>
  apiPost<SimulateRuleResponse>("/policy/simulate", { rule }, REQUEST_TIMEOUT_MS * 4);

// --- Simulation Engine ------------------------------------------------------

/**
 * Evaluates a proposed action through the whole pre-execution pipeline.
 * Nothing is persisted — what-ifs should not appear in the audit trail
 * alongside decisions that actually happened.
 */
export const runSimulation = (request: SimulateActionRequest) =>
  apiPost<SimulateActionResponse>("/simulation/run", request, REQUEST_TIMEOUT_MS * 2);

/** Appends an immutable version to a policy and activates it. */
export const createPolicyVersion = (
  policyId: string,
  payload: { rule: PolicyRule; version: string; note?: string },
) =>
  apiPost<PolicyVersion>(
    `/policy/policies/${encodeURIComponent(policyId)}/versions`,
    payload,
  );
