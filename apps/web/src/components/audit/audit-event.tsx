"use client";

import { useState } from "react";
import { ChevronRight, User } from "lucide-react";

import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { StatusChip } from "@/components/ui/status-chip";
import { AUDIT_KIND_LABELS, auditFacts, auditOutcome } from "@/lib/audit";
import type { LedgerEntry } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

/**
 * One event on the audit timeline. Collapsed it answers who, what and when;
 * expanded it adds why, and the raw evidence that was hashed.
 */
export function AuditEvent({ entry }: { entry: LedgerEntry }) {
  const [open, setOpen] = useState(false);
  const facts = auditFacts(entry);
  const outcome = auditOutcome(entry);

  return (
    <li className="relative flex gap-3">
      {/* The rail is drawn per event, so the last one stops cleanly. */}
      <div className="flex w-3 shrink-0 flex-col items-center pt-3.5">
        <span
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            outcome === "blocked"
              ? "bg-error"
              : outcome === "escalated"
                ? "bg-brand-amber"
                : outcome === "approved"
                  ? "bg-tertiary"
                  : "bg-outline",
          )}
          aria-hidden
        />
        <span className="mt-1 w-px flex-1 bg-outline-strong" aria-hidden />
      </div>

      <div className="min-w-0 flex-1 border-b border-outline-variant last:border-b-0">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="flex w-full items-center gap-3 rounded-md py-2.5 pl-1 pr-2 text-left transition-colors hover:bg-surface-container-high"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-body-md text-on-surface">{facts.what}</p>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-body-sm text-on-surface-variant">
              <span className="inline-flex items-center gap-1">
                <User className="size-3 text-outline" strokeWidth={1.75} aria-hidden />
                {facts.who}
              </span>
              {facts.agent && (
                <>
                  <span className="text-outline" aria-hidden>
                    ·
                  </span>
                  {facts.agent}
                </>
              )}
              <span className="text-outline" aria-hidden>
                ·
              </span>
              <span className="font-mono text-label-mono-xs text-outline">
                {entry.subjectId}
              </span>
            </p>
          </div>

          <span className="hidden w-[74px] shrink-0 text-right font-mono text-body-sm text-on-surface sm:block">
            {facts.amount ?? ""}
          </span>

          <span className="hidden shrink-0 lg:block">
            <StatusChip tone="neutral">
              {AUDIT_KIND_LABELS[entry.kind] ?? entry.kind}
            </StatusChip>
          </span>

          <span className="w-[104px] shrink-0">
            {outcome && <OutcomeBadge outcome={outcome} />}
          </span>

          <span className="hidden w-[68px] shrink-0 text-right font-mono text-label-mono-xs text-outline md:block">
            {formatTime(entry.recordedAt)}
          </span>

          <ChevronRight
            className={cn(
              "size-3.5 shrink-0 text-outline transition-transform",
              open && "rotate-90",
            )}
            aria-hidden
          />
        </button>

        {open && (
          <div className="mb-2.5 space-y-3.5 rounded-md border border-outline-variant bg-surface-container-high px-3.5 py-3">
            <div>
              <p className="eyebrow">Why</p>
              {facts.why.length > 0 ? (
                <ul className="mt-1.5 space-y-1">
                  {facts.why.map((line) => (
                    <li key={line} className="text-body-sm text-on-surface-variant">
                      {line}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-body-sm text-outline">
                  This entry kind records no rule evaluation.
                </p>
              )}
            </div>

            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="eyebrow">Entry hash</dt>
                <dd className="mt-1 break-all font-mono text-body-sm text-on-surface">
                  {entry.entryHash}
                </dd>
              </div>
              <div className="min-w-0">
                <dt className="eyebrow">Previous hash</dt>
                <dd className="mt-1 break-all font-mono text-body-sm text-on-surface-variant">
                  {entry.prevHash}
                </dd>
              </div>
            </dl>

            <div>
              <p className="eyebrow">Evidence, as hashed</p>
              {/* The raw payload, not a prettified summary: this is the exact
                  object that was hashed, so an auditor can recompute it. */}
              <pre className="custom-scrollbar mt-1.5 max-h-80 overflow-auto rounded-md border border-outline-variant bg-surface-base p-3 font-mono text-body-sm text-on-surface-variant">
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </li>
  );
}
