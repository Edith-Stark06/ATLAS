"use client";

import { useState } from "react";
import { BadgeCheck, ChevronRight, Scale } from "lucide-react";

import { StatusChip } from "@/components/ui/status-chip";
import type { ExplanationRule, RuleEffect } from "@/lib/types";
import { cn } from "@/lib/utils";

const EFFECT_LABELS: Record<RuleEffect, string> = {
  allow: "Allow",
  require_human_review: "Require review",
  block: "Block",
};

const EFFECT_TONE: Record<RuleEffect, "success" | "warning" | "danger"> = {
  allow: "success",
  require_human_review: "warning",
  block: "danger",
};

function RuleRow({ rule }: { rule: ExplanationRule }) {
  return (
    <li
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5",
        !rule.inScope && "opacity-60",
      )}
    >
      <span className="w-16 shrink-0 font-mono text-label-mono-xs text-outline">
        {rule.policyId}
      </span>
      <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface">
        {rule.policyName}
      </span>
      <span className="font-mono text-label-mono-xs text-outline">{rule.version}</span>
      {rule.matched && rule.effect ? (
        <StatusChip tone={EFFECT_TONE[rule.effect]}>{EFFECT_LABELS[rule.effect]}</StatusChip>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-status-label uppercase text-outline">
          {rule.inScope ? (
            <>
              <BadgeCheck className="size-3" /> No match
            </>
          ) : (
            <>
              <Scale className="size-3" /> Out of scope
            </>
          )}
        </span>
      )}
    </li>
  );
}

/**
 * The rule versions evaluated at decision time.
 *
 * Rules that were in scope come first, and among those the ones that actually
 * matched come first again — those are the answer. Rules that never applied to
 * this agent are folded away: they prove the evaluation was exhaustive, which
 * is worth being able to check and not worth reading past.
 */
export function RulesInForce({ rules }: { rules: ExplanationRule[] }) {
  const [showAll, setShowAll] = useState(false);

  const inScope = rules.filter((rule) => rule.inScope);
  const outOfScope = rules.filter((rule) => !rule.inScope);
  const ordered = [...inScope].sort((a, b) => Number(b.matched) - Number(a.matched));

  return (
    <>
      <ul className="divide-y divide-outline-variant">
        {ordered.map((rule) => (
          <RuleRow key={rule.policyId} rule={rule} />
        ))}
        {showAll && outOfScope.map((rule) => <RuleRow key={rule.policyId} rule={rule} />)}
      </ul>

      {outOfScope.length > 0 && (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          aria-expanded={showAll}
          className="flex w-full items-center gap-2 border-t border-outline-variant px-4 py-2.5 text-left text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
        >
          <ChevronRight
            className={cn(
              "size-3.5 shrink-0 text-outline transition-transform",
              showAll && "rotate-90",
            )}
            aria-hidden
          />
          {showAll ? "Hide" : "Show"} {outOfScope.length} rule
          {outOfScope.length === 1 ? "" : "s"} that were evaluated but out of scope
        </button>
      )}
    </>
  );
}
