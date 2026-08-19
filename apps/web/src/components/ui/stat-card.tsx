import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type StatTone = "primary" | "secondary" | "tertiary" | "error";

const ICON_TONE: Record<StatTone, string> = {
  primary: "text-primary",
  secondary: "text-secondary",
  tertiary: "text-tertiary",
  error: "text-error",
};

const GLOW_TONE: Record<StatTone, string> = {
  primary: "from-primary/5",
  secondary: "from-secondary/5",
  tertiary: "from-tertiary/5",
  error: "from-error/5",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "secondary",
  delta,
  className,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: StatTone;
  delta?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "glass-panel group relative flex flex-col justify-between overflow-hidden rounded-xl p-4",
        className,
      )}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-0 bg-gradient-to-br to-transparent opacity-0 transition-opacity group-hover:opacity-100",
          GLOW_TONE[tone],
        )}
      />
      <div className="mb-4 flex items-start justify-between gap-2">
        <span className="font-mono text-label-mono text-on-surface-variant">{label}</span>
        <Icon className={cn("size-[18px] shrink-0", ICON_TONE[tone])} />
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-headline-lg text-on-surface">{value}</span>
        {delta && <span className="font-mono text-label-mono text-tertiary">{delta}</span>}
      </div>
    </div>
  );
}
