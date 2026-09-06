import {
  Building2,
  FlaskConical,
  Gavel,
  Lightbulb,
  Scale,
  ScrollText,
  Send,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import type { PipelineStage, PipelineStageStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAGE_ICONS: Record<string, LucideIcon> = {
  request: Send,
  trust: ShieldCheck,
  policy: Scale,
  simulation: FlaskConical,
  decision: Gavel,
  explain: Lightbulb,
  ledger: ScrollText,
  execute: Building2,
};

const NODE_STYLES: Record<PipelineStageStatus, string> = {
  done: "border-outline-strong bg-surface-container-high text-on-surface-variant",
  // Violet marks where the pipeline currently is — the one place on this
  // component the brand colour is spent.
  active: "border-primary bg-primary/[0.12] text-primary",
  pending: "border-outline-variant bg-surface-container text-outline",
  failed: "border-error/50 bg-error/[0.08] text-error",
};

const RAIL_STYLES: Record<PipelineStageStatus, string> = {
  done: "bg-outline-strong",
  active: "bg-primary/50",
  pending: "bg-outline-variant",
  failed: "bg-error/40",
};

const LABEL_STYLES: Record<PipelineStageStatus, string> = {
  done: "text-on-surface",
  active: "text-primary",
  pending: "text-outline",
  failed: "text-error",
};

/**
 * The governance pipeline as a horizontal rail:
 * Request → Trust → Policy → Simulation → Decision → Explain → Ledger → Execution.
 *
 * The connector between two nodes takes the colour of the *earlier* stage, so
 * the rail visibly stops where the pipeline stopped.
 */
export function Pipeline({
  stages,
  /** Narrower nodes and smaller labels, for a side column. */
  dense = false,
}: {
  stages: PipelineStage[];
  dense?: boolean;
}) {
  return (
    <ol className="flex w-full items-start overflow-x-auto pb-1">
      {stages.map((stage, index) => {
        const Icon = STAGE_ICONS[stage.key] ?? Send;
        const isLast = index === stages.length - 1;

        return (
          <li
            key={stage.key}
            className={cn(
              "flex flex-1 flex-col items-center px-1.5 text-center",
              dense ? "min-w-[64px]" : "min-w-[92px]",
            )}
          >
            <div className="flex w-full items-center">
              {/* Half-rails either side keep the node centred over its label. */}
              <span
                className={cn(
                  "h-px flex-1",
                  index === 0 ? "bg-transparent" : RAIL_STYLES[stages[index - 1].status],
                )}
                aria-hidden
              />
              <span
                className={cn(
                  "flex shrink-0 items-center justify-center rounded-md border",
                  dense ? "size-6" : "size-7",
                  NODE_STYLES[stage.status],
                )}
              >
                <Icon className={dense ? "size-3" : "size-3.5"} strokeWidth={1.75} />
              </span>
              <span
                className={cn(
                  "h-px flex-1",
                  isLast ? "bg-transparent" : RAIL_STYLES[stage.status],
                )}
                aria-hidden
              />
            </div>

            <span
              className={cn(
                "mt-2 px-1 text-body-sm leading-tight",
                LABEL_STYLES[stage.status],
              )}
            >
              {stage.label}
            </span>
            {stage.detail && (
              <span
                className="mt-0.5 block w-full truncate font-mono text-label-mono-xs text-outline"
                title={stage.detail}
              >
                {stage.detail}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
