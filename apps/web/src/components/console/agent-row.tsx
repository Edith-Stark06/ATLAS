import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { LifecycleBadge, trustColor, trustFill } from "@/components/ui/lifecycle-badge";
import { Meter } from "@/components/ui/charts";
import type { Agent } from "@/lib/types";
import { cn } from "@/lib/utils";

/** 24h movement, in points. Flat below half a point — noise is not a trend. */
export function TrustDelta({ delta, className }: { delta: number; className?: string }) {
  const flat = Math.abs(delta) < 0.5;
  const Icon = flat ? Minus : delta > 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-mono text-label-mono-xs",
        flat ? "text-outline" : delta > 0 ? "text-tertiary" : "text-error",
        className,
      )}
      title="Change over the last 24 hours, in points"
    >
      <Icon className="size-3" strokeWidth={2} aria-hidden />
      {flat ? "0.0" : Math.abs(delta).toFixed(1)}
    </span>
  );
}

/**
 * A compact roster line: who the agent is, where its trust sits, which way it
 * is moving, and what state that puts it in. Deliberately not a table row —
 * the roster is a glance, and the registry is the table.
 *
 * `compact` drops the meter and the lifecycle chip. Tailwind's breakpoints are
 * viewport-wide, so a narrow *column* on a wide screen cannot be handled by
 * `sm:` — the caller has to say which shape it wants, or the name collapses to
 * a single character.
 */
export function AgentRow({ agent, compact = false }: { agent: Agent; compact?: boolean }) {
  return (
    <Link
      href={`/console/agents/${encodeURIComponent(agent.id)}`}
      className="group flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-container-high"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-body-md text-on-surface">{agent.name}</p>
        <p className="truncate text-body-sm text-outline">{agent.capability}</p>
      </div>

      {!compact && (
        <div className="hidden w-20 shrink-0 lg:block">
          <Meter value={agent.trustScore} color={trustFill(agent.trustScore)} />
        </div>
      )}

      <div className="flex w-[52px] shrink-0 items-baseline justify-end gap-0.5">
        <span className={cn("font-mono text-body-md", trustColor(agent.trustScore))}>
          {agent.trustScore}
        </span>
        <span className="font-mono text-label-mono-xs text-outline">/100</span>
      </div>

      <TrustDelta delta={agent.trustDelta} className="w-11 shrink-0 justify-end" />

      {!compact && (
        <span className="hidden shrink-0 md:block">
          <LifecycleBadge state={agent.lifecycle} />
        </span>
      )}
    </Link>
  );
}
