import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type StatTone = "primary" | "secondary" | "tertiary" | "error" | "warning";

/**
 * Tone colours the *value*, not the card. A metric is worth a colour only when
 * the number itself carries a state — blocked counts, drifting agents — and
 * plain text otherwise.
 */
const VALUE_TONE: Record<StatTone, string> = {
  primary: "text-on-surface",
  secondary: "text-on-surface",
  tertiary: "text-tertiary",
  warning: "text-brand-amber",
  error: "text-error",
};

const ICON_TONE: Record<StatTone, string> = {
  primary: "text-outline",
  secondary: "text-outline",
  tertiary: "text-tertiary/70",
  warning: "text-brand-amber/70",
  error: "text-error/70",
};

/**
 * A compact metric tile: label, figure, optional delta. Deliberately small —
 * a row of these is a summary bar, not the page's subject.
 */
export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "primary",
  delta,
  deltaTone = "neutral",
  hint,
  className,
  delay,
  /** Marks the page's headline number: larger figure, violet hairline. */
  featured = false,
}: {
  label: string;
  value: string;
  icon?: LucideIcon;
  tone?: StatTone;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  /** Denominator or unit, shown beside the figure. */
  hint?: string;
  className?: string;
  delay?: number;
  featured?: boolean;
}) {
  return (
    <div
      className={cn(
        "surface-card animate-fade-in-up flex min-h-[76px] flex-col justify-between gap-2 px-3.5 py-3",
        featured && "border-primary/25 bg-primary/[0.04]",
        className,
      )}
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="eyebrow leading-snug">{label}</span>
        {Icon && (
          <Icon className={cn("size-3.5 shrink-0", ICON_TONE[tone])} strokeWidth={1.75} />
        )}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
        <span className={cn("text-metric-num", VALUE_TONE[tone])}>{value}</span>
        {hint && <span className="text-label-mono-xs text-outline">{hint}</span>}
        {delta && (
          <span
            className={cn(
              "font-mono text-label-mono-xs",
              deltaTone === "up" && "text-tertiary",
              deltaTone === "down" && "text-error",
              deltaTone === "neutral" && "text-outline",
            )}
          >
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * The same figure without a card — for use inside a panel, where a second
 * border would just be noise.
 */
export function Metric({
  label,
  value,
  hint,
  tone = "primary",
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: StatTone;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="eyebrow">{label}</p>
      <p className={cn("mt-1 text-metric-num", VALUE_TONE[tone])}>{value}</p>
      {hint && <p className="mt-0.5 text-body-sm text-outline">{hint}</p>}
    </div>
  );
}
