"use client";

import { useState } from "react";
import { ChevronRight, Link2 } from "lucide-react";

import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { StatusChip } from "@/components/ui/status-chip";
import type { DecisionOutcome, LedgerEntry } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

const KIND_LABELS: Record<string, string> = {
  decision_recorded: "Decision",
  policy_activated: "Policy",
  trust_recomputed: "Trust",
};

const OUTCOMES = new Set(["approved", "escalated", "blocked"]);

/** Reads the outcome out of a decision payload without trusting its shape —
 * payloads vary by kind and older entries may predate a field. */
function outcomeOf(entry: LedgerEntry): DecisionOutcome | null {
  const decision = entry.payload?.decision as { outcome?: unknown } | undefined;
  const outcome = decision?.outcome;
  return typeof outcome === "string" && OUTCOMES.has(outcome)
    ? (outcome as DecisionOutcome)
    : null;
}

function actionOf(entry: LedgerEntry): string {
  const decision = entry.payload?.decision as { action?: unknown } | undefined;
  return typeof decision?.action === "string" ? decision.action : entry.subjectId;
}

/** First and last 8 characters — enough to compare two hashes by eye, short
 * enough to sit in a table row. The full value is one click away. */
function abbreviate(hash: string): string {
  return `${hash.slice(0, 8)}…${hash.slice(-8)}`;
}

export function LedgerEntryRow({ entry }: { entry: LedgerEntry }) {
  const [open, setOpen] = useState(false);
  const outcome = outcomeOf(entry);

  return (
    <li className="border-b border-white/5 last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-3 px-6 py-3 text-left transition-colors hover:bg-white/[0.02]"
      >
        <ChevronRight
          className={cn(
            "size-4 shrink-0 text-outline transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="font-mono text-body-sm text-outline">#{entry.seq}</span>
        <StatusChip tone="neutral">{KIND_LABELS[entry.kind] ?? entry.kind}</StatusChip>
        {/* basis-48, not just flex-1: with min-w-0 alone this column collapses
            to a single character when the row is tight, instead of wrapping. */}
        <span className="min-w-0 flex-1 basis-48 truncate text-body-sm text-on-surface">
          {actionOf(entry)}
        </span>
        <span
          className="hidden font-mono text-status-label text-outline lg:inline"
          title={entry.entryHash}
        >
          {abbreviate(entry.entryHash)}
        </span>
        <span className="font-mono text-status-label text-outline">
          {formatTime(entry.recordedAt)}
        </span>
        {outcome && <OutcomeBadge outcome={outcome} />}
      </button>

      {open && (
        <div className="border-t border-white/5 bg-surface-container-high/30 px-6 py-4">
          <dl className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                Entry hash
              </dt>
              <dd className="mt-1 break-all font-mono text-body-sm text-on-surface">
                {entry.entryHash}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1.5 font-mono text-status-label uppercase text-on-surface-variant">
                <Link2 className="size-3" /> Previous hash
              </dt>
              <dd className="mt-1 break-all font-mono text-body-sm text-on-surface-variant">
                {entry.prevHash}
              </dd>
            </div>
          </dl>

          <p className="mb-2 font-mono text-status-label uppercase text-on-surface-variant">
            Pinned evidence
          </p>
          {/* The raw payload, not a prettified summary: this is the exact
              object that was hashed, so an auditor can recompute it. */}
          <pre className="max-h-96 overflow-auto rounded border border-white/5 bg-surface-base/60 p-4 font-mono text-body-sm text-on-surface-variant">
            {JSON.stringify(entry.payload, null, 2)}
          </pre>
        </div>
      )}
    </li>
  );
}
