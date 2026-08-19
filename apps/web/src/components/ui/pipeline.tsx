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
  done: "border-tertiary/60 bg-tertiary/10 text-tertiary",
  active: "border-primary bg-primary/15 text-primary shadow-[0_0_12px_-2px_var(--color-primary)] animate-pulse",
  pending: "border-outline-variant bg-surface-container text-on-surface-variant",
  failed: "border-error/60 bg-error/10 text-error",
};

const LABEL_STYLES: Record<PipelineStageStatus, string> = {
  done: "text-on-surface",
  active: "text-primary",
  pending: "text-on-surface-variant/60",
  failed: "text-error",
};

/**
 * The ATLAS governance pipeline, rendered left-to-right:
 * Agent Request → Trust → Policy → Simulation → Decision → Explain → Ledger → Execution.
 */
export function Pipeline({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="relative flex w-full items-start justify-between gap-2 overflow-x-auto pb-2">
      {/* Rail sits behind the nodes, aligned to their vertical centre. */}
      <div className="absolute left-0 top-4 -z-0 h-px w-full bg-outline-variant/30" />

      {stages.map((stage) => {
        const Icon = STAGE_ICONS[stage.key] ?? Send;
        return (
          <div
            key={stage.key}
            className="relative z-10 flex min-w-[80px] flex-1 flex-col items-center text-center"
          >
            <div
              className={cn(
                "mb-2 flex size-8 items-center justify-center rounded-full border",
                NODE_STYLES[stage.status],
              )}
            >
              <Icon className="size-4" />
            </div>
            <span
              className={cn(
                "font-mono text-status-label leading-tight",
                LABEL_STYLES[stage.status],
              )}
            >
              {stage.label}
            </span>
            {stage.detail && (
              <span className="mt-1 font-mono text-status-label text-outline">
                {stage.detail}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
