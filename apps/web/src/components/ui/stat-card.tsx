import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type StatTone = "primary" | "secondary" | "tertiary" | "error";

const ICON_TONE: Record<StatTone, string> = {
  primary: "text-primary drop-shadow-[0_0_5px_rgb(173_198_255_/_0.5)]",
  secondary: "text-secondary drop-shadow-[0_0_5px_rgb(76_215_246_/_0.5)]",
  tertiary: "text-tertiary-green drop-shadow-[0_0_5px_rgb(78_222_163_/_0.5)]",
  error: "text-error drop-shadow-[0_0_5px_rgb(255_180_171_/_0.5)]",
};

const GLOW_TONE: Record<StatTone, string> = {
  primary: "from-primary/10",
  secondary: "from-secondary/10",
  tertiary: "from-tertiary-green/10",
  error: "from-error/10",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "secondary",
  delta,
  className,
  delay,
  /** Marks this as the headline metric — ringed, glowing, larger numeral. */
  featured = false,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: StatTone;
  delta?: string;
  className?: string;
  delay?: number;
  featured?: boolean;
}) {
  return (
    <div
      className={cn(
        "glass-panel glass-panel-hover group relative flex animate-fade-in-up flex-col justify-between overflow-hidden rounded-xl p-5",
        featured &&
          "bg-surface-container/60 ring-1 ring-cyan-glow/30 shadow-[0_0_20px_rgb(6_182_212_/_0.15)]",
        className,
      )}
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-0 bg-gradient-to-br to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100",
          GLOW_TONE[tone],
        )}
      />
      <div className="relative z-10 mb-4 flex items-start justify-between gap-2">
        <span
          className={cn(
            "font-mono text-label-mono transition-colors",
            featured ? "text-white" : "text-on-surface-variant group-hover:text-white",
          )}
        >
          {label}
        </span>
        <Icon className={cn("size-5 shrink-0", ICON_TONE[tone])} />
      </div>
      <div className="relative z-10 flex items-baseline gap-2">
        <span
          className={cn(
            "tracking-tighter",
            featured
              ? "text-[56px] font-bold leading-none text-white drop-shadow-[0_0_10px_rgb(255_255_255_/_0.5)]"
              : "counter-gradient text-hero-num",
          )}
        >
          {value}
        </span>
        {delta && <span className="font-mono text-label-mono text-tertiary-green">{delta}</span>}
      </div>
    </div>
  );
}
