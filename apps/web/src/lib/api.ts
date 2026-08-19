export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export async function fetchHealth(): Promise<HealthProbe> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });

    if (!res.ok) {
      return { reachable: false, error: `API responded ${res.status}` };
    }

    return { reachable: true, data: (await res.json()) as HealthResponse };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { reachable: false, error: message };
  }
}
