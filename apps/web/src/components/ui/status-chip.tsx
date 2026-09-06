import { cn } from "@/lib/utils";

export type ChipTone = "success" | "warning" | "danger" | "info" | "brand" | "neutral";

/**
 * Outlined, not filled. A tinted background on every badge turns a dense table
 * into a colour field; a hairline border in the semantic colour says the same
 * thing without competing with the data.
 */
const TONE_STYLES: Record<ChipTone, string> = {
  success: "border-tertiary/35 text-tertiary",
  warning: "border-brand-amber/35 text-brand-amber",
  danger: "border-error/40 text-error",
  brand: "border-primary/35 text-primary",
  info: "border-outline-strong text-on-surface-variant",
  neutral: "border-outline-variant text-outline",
};

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
        "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-status-label uppercase leading-none",
        TONE_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
