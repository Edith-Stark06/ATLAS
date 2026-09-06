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

import { cn } from "@/lib/utils";

interface Stage {
  label: string;
  detail: string;
  icon: LucideIcon;
  /** The three stages that do the actual deciding carry the accent. */
  emphasis?: boolean;
}

const STAGES: Stage[] = [
  { label: "Request", detail: "An agent asks to act", icon: Send },
  {
    label: "Trust",
    detail: "Is this agent trustworthy right now?",
    icon: ShieldCheck,
    emphasis: true,
  },
  { label: "Policy", detail: "Do the rules permit it?", icon: Scale, emphasis: true },
  {
    label: "Simulation",
    detail: "What happens if we allow it?",
    icon: FlaskConical,
    emphasis: true,
  },
  { label: "Decision", detail: "Approve, escalate, or block", icon: Gavel },
  { label: "Explain", detail: "Why, in plain language", icon: Lightbulb },
  { label: "Ledger", detail: "Recorded immutably", icon: ScrollText },
  { label: "Execution", detail: "Only now does it run", icon: Building2 },
];

/**
 * The governance pipeline, as the product's core claim: every one of these
 * stages happens *before* the action executes.
 *
 * Horizontal on desktop over a hairline rail; vertical below `lg`, where eight
 * nodes in a row would be unreadable.
 */
export function PipelineDiagram() {
  return (
    <div className="relative">
      {/* Connector rail — behind the nodes, aligned to their centres. */}
      <div
        className="absolute left-0 top-[19px] hidden h-px w-full bg-outline-variant lg:block"
        aria-hidden
      />

      <ol className="relative flex flex-col gap-5 lg:flex-row lg:justify-between lg:gap-2">
        {STAGES.map((stage) => (
          <li
            key={stage.label}
            className="flex items-center gap-4 lg:max-w-[10rem] lg:flex-1 lg:flex-col lg:items-center lg:gap-0 lg:text-center"
          >
            <span
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-md border",
                stage.emphasis
                  ? "border-primary/40 bg-primary/[0.08] text-primary"
                  : "border-outline-variant bg-surface-container text-outline",
              )}
            >
              <stage.icon className="size-4" strokeWidth={1.75} />
            </span>
            <div className="lg:mt-3">
              <p
                className={cn(
                  "text-body-md font-medium",
                  stage.emphasis ? "text-on-surface" : "text-on-surface-variant",
                )}
              >
                {stage.label}
              </p>
              <p className="mt-0.5 text-body-sm text-outline">{stage.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
