"use client";

import { useState } from "react";
import { Check, ChevronRight, X } from "lucide-react";

import type { PolicyCheck } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * A rule that was evaluated but never applied to this agent tells you nothing
 * about why the decision came out as it did. With 23 policies registered and
 * one of them binding, listing all 23 flat buries the answer.
 */
function isOutOfScope(check: PolicyCheck): boolean {
  return (check.detail ?? "").toLowerCase().includes("out of scope");
}

function CheckRow({ check }: { check: PolicyCheck }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
      {check.passed ? (
        <Check className="size-3.5 shrink-0 text-tertiary" strokeWidth={2} />
      ) : (
        <X className="size-3.5 shrink-0 text-error" strokeWidth={2} />
      )}
      <span className="w-52 shrink-0 truncate text-body-sm text-on-surface">
        {check.policyName}
      </span>
      <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface-variant">
        {check.detail ?? "—"}
      </span>
      <span className="font-mono text-label-mono-xs text-outline">{check.policyId}</span>
    </li>
  );
}

/**
 * Policy evidence for one decision.
 *
 * Rules that were actually in scope are shown; the ones that never applied to
 * this agent are counted and folded away, because their only job here is to
 * prove the evaluation was exhaustive — not to be read.
 */
export function PolicyEvidence({ checks }: { checks: PolicyCheck[] }) {
  const [showAll, setShowAll] = useState(false);

  if (checks.length === 0) {
    return (
      <p className="text-body-sm text-outline">No policy was in scope for this action.</p>
    );
  }

  const outOfScope = checks.filter(isOutOfScope);
  const inScope = checks.filter((check) => !isOutOfScope(check));
  // Failures first: the binding rule is the answer, and it should be the first
  // thing read rather than something to scroll for.
  const ordered = [...inScope].sort(
    (a, b) => Number(a.passed) - Number(b.passed),
  );

  return (
    <div className="overflow-hidden rounded-md border border-outline-variant">
      <ul className="divide-y divide-outline-variant">
        {ordered.map((check) => (
          <CheckRow key={check.policyId} check={check} />
        ))}
        {showAll &&
          outOfScope.map((check) => <CheckRow key={check.policyId} check={check} />)}
      </ul>

      {outOfScope.length > 0 && (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          aria-expanded={showAll}
          className="flex w-full items-center gap-2 border-t border-outline-variant px-3 py-2 text-left text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
        >
          <ChevronRight
            className={cn("size-3.5 shrink-0 text-outline transition-transform", showAll && "rotate-90")}
            aria-hidden
          />
          {showAll ? "Hide" : "Show"} {outOfScope.length} rule
          {outOfScope.length === 1 ? "" : "s"} evaluated but out of scope for this
          agent&apos;s capability
        </button>
      )}
    </div>
  );
}
