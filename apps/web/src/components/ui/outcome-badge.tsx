import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import type { DecisionOutcome } from "@/lib/types";

const OUTCOME_META: Record<DecisionOutcome, { label: string; tone: ChipTone }> = {
  approved: { label: "Approved", tone: "success" },
  escalated: { label: "Escalated", tone: "warning" },
  blocked: { label: "Blocked", tone: "danger" },
};

export function OutcomeBadge({ outcome }: { outcome: DecisionOutcome }) {
  const meta = OUTCOME_META[outcome];
  return <StatusChip tone={meta.tone}>{meta.label}</StatusChip>;
}

/** Colour for a 0–100 risk score (higher is worse — inverse of trust). */
export function riskColor(score: number): string {
  if (score >= 75) return "text-error";
  if (score >= 50) return "text-brand-amber";
  if (score >= 25) return "text-primary";
  return "text-tertiary";
}
