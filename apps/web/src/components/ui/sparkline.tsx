import { TrendLine } from "@/components/ui/charts";

/**
 * Thin wrapper kept for the call sites that predate `charts.tsx`. New code
 * should use `TrendLine` directly, which this is.
 */
export function Sparkline({
  values,
  stroke = "var(--color-primary)",
  className,
  gradientId = "sparkline-gradient",
  animate = true,
}: {
  values: number[];
  stroke?: string;
  className?: string;
  /** Unique per instance — SVG gradient ids are document-global. */
  gradientId?: string;
  /** Retained for compatibility; the draw-in is always short and reduced-motion aware. */
  animate?: boolean;
}) {
  void animate;
  return (
    <TrendLine
      values={values}
      color={stroke}
      className={className}
      gradientId={gradientId}
    />
  );
}
