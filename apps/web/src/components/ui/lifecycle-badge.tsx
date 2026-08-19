import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import type { LifecycleState } from "@/lib/types";

const LIFECYCLE_META: Record<LifecycleState, { label: string; tone: ChipTone }> = {
  onboarding: { label: "Onboarding", tone: "info" },
  healthy: { label: "Healthy", tone: "success" },
  trusted: { label: "Trusted", tone: "success" },
  anomaly: { label: "Anomaly", tone: "warning" },
  review: { label: "Under Review", tone: "warning" },
  recovery: { label: "Recovery", tone: "info" },
};

export function LifecycleBadge({ state }: { state: LifecycleState }) {
  const meta = LIFECYCLE_META[state];
  return <StatusChip tone={meta.tone}>{meta.label}</StatusChip>;
}

/** Colour for a 0–100 trust score, matching the trust bands. */
export function trustColor(score: number): string {
  if (score >= 90) return "text-tertiary";
  if (score >= 75) return "text-primary";
  if (score >= 60) return "text-brand-amber";
  return "text-error";
}
