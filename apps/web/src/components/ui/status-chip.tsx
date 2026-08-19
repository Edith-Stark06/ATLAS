import { cn } from "@/lib/utils";

export type ChipTone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_STYLES: Record<ChipTone, string> = {
  success: "bg-tertiary/10 text-tertiary",
  warning: "bg-brand-amber/10 text-brand-amber",
  danger: "bg-error/10 text-error",
  info: "bg-secondary/10 text-secondary",
  neutral: "bg-outline/10 text-on-surface-variant",
};

/**
 * Low-profile status badge — 10% tint of the semantic colour, per the
 * design system's chip spec.
 */
export function StatusChip({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: ChipTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-xl px-2 py-1 text-status-label uppercase",
        TONE_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
