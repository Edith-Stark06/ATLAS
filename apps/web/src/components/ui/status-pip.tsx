import { cn } from "@/lib/utils";

export type PipTone = "up" | "down" | "warn" | "idle" | "brand";

const TONE_STYLES: Record<PipTone, string> = {
  up: "bg-tertiary",
  down: "bg-error",
  warn: "bg-brand-amber",
  brand: "bg-primary",
  idle: "bg-outline",
};

/**
 * A 6px state dot. No halo: the colour is the signal, and a glow on every
 * status indicator is exactly the "AI dashboard" tell this design avoids.
 * `pulse` is reserved for genuinely live things (an open stream), where the
 * motion means "this is still connected".
 */
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
    <span className={cn("relative inline-flex size-1.5 shrink-0", className)} aria-hidden>
      {pulse && (
        <span
          className={cn(
            "absolute inset-0 animate-ping rounded-full opacity-60",
            TONE_STYLES[tone],
          )}
        />
      )}
      <span className={cn("relative inline-block size-1.5 rounded-full", TONE_STYLES[tone])} />
    </span>
  );
}
