import { cn } from "@/lib/utils";

export type PipTone = "up" | "down" | "warn" | "idle";

const TONE_STYLES: Record<PipTone, string> = {
  up: "bg-tertiary shadow-[0_0_8px_0_var(--color-tertiary)]",
  down: "bg-error shadow-[0_0_8px_0_var(--color-error)]",
  warn: "bg-brand-amber shadow-[0_0_8px_0_var(--color-brand-amber)]",
  idle: "bg-outline",
};

/** "Glow-Pip" status indicator — small dot with a matching colour halo. */
export function StatusPip({
  tone,
  pulse = false,
  className,
}: {
  tone: PipTone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block size-1.5 shrink-0 rounded-full",
        TONE_STYLES[tone],
        pulse && "animate-pulse",
        className,
      )}
      aria-hidden
    />
  );
}
