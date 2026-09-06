import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { OutcomeBadge } from "@/components/ui/outcome-badge";
import type { Decision } from "@/lib/types";
import { cn, formatTime, formatUsd } from "@/lib/utils";

const EDGE_TONE: Record<Decision["outcome"], string> = {
  approved: "before:bg-tertiary",
  escalated: "before:bg-brand-amber",
  blocked: "before:bg-error",
};

/**
 * One governed action, compact enough that a dozen fit on screen.
 *
 * Agent, what it asked to do, what it would cost, the verdict, when. No
 * prose — the reasoning lives one click deeper, in the investigation.
 */
export function DecisionCard({
  decision,
  className,
}: {
  decision: Decision;
  className?: string;
}) {
  return (
    <Link
      href={`/console/decisions/${encodeURIComponent(decision.id)}`}
      className={cn(
        "group relative flex items-center gap-3 py-2.5 pl-4 pr-3 transition-colors hover:bg-surface-container-high",
        // A 2px verdict edge on the left: in a scrolling list the state is
        // legible before any of the text is read.
        "before:absolute before:inset-y-1.5 before:left-0 before:w-[2px] before:rounded-r-full",
        EDGE_TONE[decision.outcome],
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="truncate text-body-md font-medium text-on-surface">
            {decision.agentName}
          </span>
          <span className="shrink-0 font-mono text-label-mono-xs text-outline">
            {decision.id}
          </span>
        </div>
        <p className="mt-0.5 truncate text-body-sm text-on-surface-variant">
          {decision.action}
        </p>
      </div>

      {/* The slot is reserved even when there is no amount, so the verdicts
          below it stay in one column instead of ragging. */}
      <span className="hidden w-[74px] shrink-0 text-right font-mono text-body-sm text-on-surface sm:block">
        {decision.amountUsd === null ? "" : formatUsd(decision.amountUsd)}
      </span>

      <span className="w-[104px] shrink-0">
        <OutcomeBadge outcome={decision.outcome} />
      </span>

      <span className="hidden w-[68px] shrink-0 text-right font-mono text-label-mono-xs text-outline md:block">
        {formatTime(decision.decidedAt)}
      </span>

      <ArrowUpRight
        className="size-3.5 shrink-0 text-outline opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
    </Link>
  );
}
