// Server-only: this module reads the session cookie. `server-only` turns an
// accidental client import into a build error naming the file, rather than a
// confusing runtime failure about `next/headers`.
import "server-only";

import { getToken } from "@/lib/session";
import type {
  ActivityItem,
  Agent,
  DashboardData,
  Decision,
  EvaluateRequest,
  EvaluateResponse,
  ExecuteDecisionRequest,
  ExecuteDecisionResponse,
  LedgerEntry,
  LedgerStats,
  LedgerVerification,
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

/**
 * Where this server reaches the ATLAS API.
 *
 * Read at runtime, and server-side only: browser code goes through
 * `/api/atlas/...` (see lib/api-client.ts), so this never has to be an address
 * a browser can resolve. In Docker that means the internal service name —
 * `http://api:8000` — and the API needs no published port at all.
 *
 * `NEXT_PUBLIC_API_URL` is still honoured as a fallback so existing local
 * `.env` files keep working, but prefer `ATLAS_API_URL`: a `NEXT_PUBLIC_`
 * value is inlined into the client bundle at build time, which makes it both
 * unchangeable at runtime and visible to anyone who views source.
 */
export const API_BASE_URL =
  process.env.ATLAS_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

/**
 * Where a request goes, and what authenticates it.
 *
 * Server-side only: the session token lives in an httpOnly cookie, so it can
 * be read here but never in the browser. Client components use
 * `lib/api-client.ts`, which routes through `/api/atlas/...` so the token is
 * attached server-side and page scripts never hold it.
 */
async function resolveRequest(path: string): Promise<{ url: string; headers: HeadersInit }> {
  const token = await getToken();

  return {
    url: `${API_BASE_URL}/api/v1${path}`,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  };
}

async function apiGet<T>(path: string): Promise<T> {
  const { url, headers } = await resolveRequest(path);

  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Cannot reach ATLAS API at ${API_BASE_URL} — ${message}`);
  }

  if (!res.ok) {
    if (res.status === 401) {
      throw new ApiError("Your session has expired — sign in again.", 401);
    }
    if (res.status === 403) {
      throw new ApiError("Your role does not permit this.", 403);
    }
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
  const { url, headers } = await resolveRequest(path);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
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

// --- Decision pipeline & governance ledger -----------------------------------

/**
 * Runs an action through the pipeline and commits it. Unlike `runSimulation`,
 * this writes a decision, its policy checks and an append-only ledger entry.
 */
export const executeDecision = (request: ExecuteDecisionRequest) =>
  apiPost<ExecuteDecisionResponse>("/decisions/execute", request, REQUEST_TIMEOUT_MS * 2);

export const fetchLedger = (params: { limit?: number; subjectId?: string } = {}) => {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  if (params.subjectId) query.set("subjectId", params.subjectId);
  const suffix = query.toString();
  return apiGet<LedgerEntry[]>(`/ledger${suffix ? `?${suffix}` : ""}`);
};

/** Recomputes every hash and checks every link — never a cached flag. */
export const verifyLedger = () => apiGet<LedgerVerification>("/ledger/verify");
export const fetchLedgerStats = () => apiGet<LedgerStats>("/ledger/stats");

/** Appends an immutable version to a policy and activates it. */
export const createPolicyVersion = (
  policyId: string,
  payload: { rule: PolicyRule; version: string; note?: string },
) =>
  apiPost<PolicyVersion>(
    `/policy/policies/${encodeURIComponent(policyId)}/versions`,
    payload,
  );
