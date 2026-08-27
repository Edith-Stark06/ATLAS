/**
 * Browser-side API access.
 *
 * Deliberately separate from `lib/api.ts`, which is server-only. That module
 * reads the session token from an httpOnly cookie via `next/headers`, and a
 * client component that imported it — even behind a `typeof window` guard —
 * would drag `server-only` into the browser bundle and fail to compile.
 *
 * The split follows the real boundary. Requests here carry no credential of
 * their own: they go to `/api/atlas/...`, and the route handler there attaches
 * the token server-side. Page scripts therefore never hold anything an XSS bug
 * could steal.
 */

import type {
  CapacityPlan,
  CapacityRequest,
  ExecuteDecisionRequest,
  ExecuteDecisionResponse,
  PolicyRule,
  PolicyVersion,
  SimulateActionRequest,
  SimulateActionResponse,
  SimulateRuleResponse,
} from "@/lib/types";

const REQUEST_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function post<T>(path: string, body: unknown, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/atlas${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
      body: JSON.stringify(body),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(`Request failed — ${message}`);
  }

  if (!res.ok) {
    if (res.status === 401) {
      throw new ApiError("Your session has expired — sign in again.", 401);
    }
    if (res.status === 403) {
      throw new ApiError("Your role does not permit this.", 403);
    }
    // 422 carries the engine's own validation message, which is far more
    // useful to an author than a generic status line.
    let detail = `Request failed with ${res.status}`;
    try {
      const parsed = await res.json();
      if (typeof parsed?.detail === "string") detail = parsed.detail;
    } catch {
      // Non-JSON error body — keep the status line.
    }
    throw new ApiError(detail, res.status);
  }

  return (await res.json()) as T;
}

/** Projects what growing a job would demand of governance. Read-only. */
export const planCapacity = (request: CapacityRequest) =>
  post<CapacityPlan>("/capacity/plan", request, REQUEST_TIMEOUT_MS * 2);

/** Evaluates a proposed action end to end. Nothing is persisted. */
export const runSimulation = (request: SimulateActionRequest) =>
  post<SimulateActionResponse>("/simulation/run", request);

/** Commits an action: writes a decision, its checks, and a ledger entry. */
export const executeDecision = (request: ExecuteDecisionRequest) =>
  post<ExecuteDecisionResponse>("/decisions/execute", request);

/** Replays a candidate rule over stored decisions before it is deployed. */
export const simulatePolicyRule = (rule: PolicyRule) =>
  post<SimulateRuleResponse>("/policy/simulate", { rule }, REQUEST_TIMEOUT_MS * 2);

/** Appends an immutable version to a policy and activates it. */
export const createPolicyVersion = (
  policyId: string,
  payload: { rule: PolicyRule; version: string; note?: string },
) => post<PolicyVersion>(`/policy/policies/${encodeURIComponent(policyId)}/versions`, payload);
