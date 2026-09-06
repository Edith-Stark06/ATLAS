import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import type { LifecycleState } from "@/lib/types";

const LIFECYCLE_META: Record<LifecycleState, { label: string; tone: ChipTone }> = {
  onboarding: { label: "Onboarding", tone: "info" },
  healthy: { label: "Healthy", tone: "success" },
  trusted: { label: "Trusted", tone: "success" },
  anomaly: { label: "Anomaly", tone: "danger" },
  review: { label: "Review", tone: "warning" },
  recovery: { label: "Recovery", tone: "info" },
};

export function LifecycleBadge({ state }: { state: LifecycleState }) {
  const meta = LIFECYCLE_META[state];
  return <StatusChip tone={meta.tone}>{meta.label}</StatusChip>;
}

/**
 * Colour for a 0–100 trust score.
 *
 * Only the two ends are coloured: a healthy score is plain text, because
 * painting every number green means none of them stand out when one is not.
 */
export function trustColor(score: number): string {
  if (score >= 90) return "text-tertiary";
  if (score >= 75) return "text-on-surface";
  if (score >= 60) return "text-brand-amber";
  return "text-error";
}

/** The band's bar/dot fill, matching `trustColor`. */
export function trustFill(score: number): string {
  if (score >= 90) return "bg-tertiary";
  if (score >= 75) return "bg-on-surface-variant";
  if (score >= 60) return "bg-brand-amber";
  return "bg-error";
}
