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
  /** The three stages that do the actual deciding get the accent treatment. */
  emphasis?: boolean;
}

const STAGES: Stage[] = [
  { label: "Agent Request", detail: "An agent asks to act", icon: Send },
  {
    label: "Trust Engine",
    detail: "Is this agent trustworthy right now?",
    icon: ShieldCheck,
    emphasis: true,
  },
  {
    label: "Policy Brain",
    detail: "Do the rules permit it?",
    icon: Scale,
    emphasis: true,
  },
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
 * Horizontal on desktop with a flowing connector rail; vertical on mobile,
 * where eight nodes in a row would be unreadable.
 */
export function PipelineDiagram() {
  return (
    <div className="relative">
      {/* Connector rail — behind the nodes, aligned to their centres. */}
      <div
        className="absolute left-0 top-6 hidden h-px w-full lg:block"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgb(6 182 212 / 0.3) 15%, rgb(6 182 212 / 0.6) 50%, rgb(78 222 163 / 0.4) 85%, transparent 100%)",
        }}
        aria-hidden
      />

      <ol className="relative flex flex-col gap-6 lg:flex-row lg:justify-between lg:gap-2">
        {STAGES.map((stage, i) => (
          <li
            key={stage.label}
            className="flex animate-fade-in-up items-center gap-4 lg:max-w-[11rem] lg:flex-1 lg:flex-col lg:items-center lg:gap-0 lg:text-center"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <span
              className={cn(
                "flex size-12 shrink-0 items-center justify-center rounded-full border backdrop-blur-md lg:size-12",
                stage.emphasis
                  ? "border-cyan-glow/50 bg-cyan-glow/10 text-cyan-glow shadow-[0_0_20px_rgb(6_182_212_/_0.25)]"
                  : "border-white/10 bg-surface-container/80 text-on-surface-variant",
              )}
            >
              <stage.icon className="size-5" />
            </span>
            <div className="lg:mt-4">
              <p
                className={cn(
                  "text-body-md font-semibold",
                  stage.emphasis ? "text-white" : "text-on-surface",
                )}
              >
                {stage.label}
              </p>
              <p className="mt-1 text-body-sm text-on-surface-variant lg:text-status-label">
                {stage.detail}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
