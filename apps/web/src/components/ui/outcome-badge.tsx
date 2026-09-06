import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

const OUTCOME_META: Record<DecisionOutcome, { label: string; tone: ChipTone; dot: string }> = {
  approved: { label: "Approved", tone: "success", dot: "bg-tertiary" },
  escalated: { label: "Escalated", tone: "warning", dot: "bg-brand-amber" },
  blocked: { label: "Blocked", tone: "danger", dot: "bg-error" },
};

/**
 * The three verdicts ATLAS can return. A leading dot carries the state at a
 * glance in a long list, where the word is read second.
 */
export function OutcomeBadge({
  outcome,
  className,
}: {
  outcome: DecisionOutcome;
  className?: string;
}) {
  const meta = OUTCOME_META[outcome];
  return (
    <StatusChip tone={meta.tone} className={className}>
      <span className={cn("size-1.5 shrink-0 rounded-full", meta.dot)} aria-hidden />
      {meta.label}
    </StatusChip>
  );
}

/** Colour for a 0–100 risk score (higher is worse — inverse of trust). */
export function riskColor(score: number): string {
  if (score >= 75) return "text-error";
  if (score >= 50) return "text-brand-amber";
  return "text-on-surface";
}
