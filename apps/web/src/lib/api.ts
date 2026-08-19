import type {
  ActivityItem,
  Agent,
  DashboardData,
  Decision,
  Policy,
  SimulationRun,
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
