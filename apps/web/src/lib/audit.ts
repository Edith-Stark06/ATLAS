import type { DecisionOutcome, LedgerEntry } from "@/lib/types";
import { formatUsd } from "@/lib/utils";

/**
 * Reading an audit event out of a ledger entry.
 *
 * Pure, and deliberately in `lib` rather than beside the row component: the
 * row is a client component (it expands), but the audit page is a server
 * component that needs these same facts to summarise the timeline. A function
 * exported from a "use client" module cannot be called on the server.
 *
 * Every read here is defensive. Payload shape varies by kind and older entries
 * may predate a field; a missing value shows as unknown rather than being
 * invented, because an audit record that guesses is worse than one that admits
 * the gap.
 */

const OUTCOMES = new Set(["approved", "escalated", "blocked"]);

export const AUDIT_KIND_LABELS: Record<string, string> = {
  decision_recorded: "Decision",
  policy_activated: "Policy change",
  trust_recomputed: "Trust recompute",
};

function section(entry: LedgerEntry, key: string): Record<string, unknown> {
  const value = entry.payload?.[key];
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function auditOutcome(entry: LedgerEntry): DecisionOutcome | null {
  const outcome = section(entry, "decision").outcome;
  return typeof outcome === "string" && OUTCOMES.has(outcome)
    ? (outcome as DecisionOutcome)
    : null;
}

/** The four questions an audit event has to answer. */
export interface AuditFacts {
  who: string;
  what: string;
  agent: string | null;
  amount: string | null;
  why: string[];
}

export function auditFacts(entry: LedgerEntry): AuditFacts {
  const decision = section(entry, "decision");
  const policy = section(entry, "policy");
  const inputs = section(entry, "inputs");

  const why: string[] = [];

  const effect = str(policy.effect);
  if (effect) {
    const readable = effect.replace(/_/g, " ");
    why.push(
      policy.forced === true
        ? `A policy rule was binding: it required "${readable}".`
        : `The active rule set returned "${readable}".`,
    );
  }

  const evaluated = Array.isArray(policy.evaluated) ? policy.evaluated : [];
  if (evaluated.length > 0) {
    const matched = evaluated.filter(
      (item) => (item as { matched?: unknown }).matched === true,
    );
    why.push(
      `${matched.length} of ${evaluated.length} policies in scope matched, at the versions recorded here.`,
    );
  }

  if (typeof inputs.trustScore === "number" && typeof inputs.riskScore === "number") {
    why.push(`Judged at trust ${inputs.trustScore} and risk ${inputs.riskScore}.`);
  }

  // Amounts are pinned as strings so the hash cannot depend on float repr.
  const amountRaw = decision.amountUsd;
  const amount =
    typeof amountRaw === "string" && amountRaw !== ""
      ? formatUsd(Number(amountRaw))
      : typeof amountRaw === "number"
        ? formatUsd(amountRaw)
        : null;

  return {
    who: str(decision.actor) ?? "system",
    what: str(decision.action) ?? entry.subjectId,
    agent: str(decision.agentName),
    amount,
    why,
  };
}
