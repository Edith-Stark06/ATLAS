import { trustColor, trustFill } from "@/components/ui/lifecycle-badge";
import { Meter } from "@/components/ui/charts";
import type { TrustFactor } from "@/lib/types";
import { cn } from "@/lib/utils";

const SIZE = 116;
const THICKNESS = 6;
/** Three-quarter sweep, so the gap reads as a scale rather than a full ring. */
const SWEEP = 0.75;

function strokeFor(score: number): string {
  if (score >= 90) return "var(--color-tertiary)";
  if (score >= 75) return "var(--color-primary)";
  if (score >= 60) return "var(--color-brand-amber)";
  return "var(--color-error)";
}

/** The score alone, as a swept arc. */
export function TrustDial({
  score,
  size = SIZE,
  label,
  className,
}: {
  score: number;
  size?: number;
  label?: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = (size - THICKNESS) / 2;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * SWEEP;
  const filled = arc * (clamped / 100);

  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label ?? "Trust"}: ${score} of 100`}
    >
      {/* Rotated 135° so the 25% gap sits at the bottom, centred. */}
      <svg viewBox={`0 0 ${size} ${size}`} className="size-full rotate-[135deg]">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-container-highest)"
          strokeWidth={THICKNESS}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circumference}`}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeFor(clamped)}
          strokeWidth={THICKNESS}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-hero-num", trustColor(clamped))}>{score}</span>
        <span className="mt-0.5 font-mono text-label-mono-xs text-outline">/ 100</span>
      </div>
    </div>
  );
}

/** The weighted factors that produced a score, each as a bar. */
export function TrustFactors({
  factors,
  className,
}: {
  factors: TrustFactor[];
  className?: string;
}) {
  return (
    <dl className={cn("min-w-0 space-y-2", className)}>
      {factors.map((factor) => (
        <div key={factor.key} className="flex items-center gap-2.5">
          <dt
            className="w-[14ch] shrink-0 truncate text-body-sm text-on-surface-variant"
            title={factor.label}
          >
            {factor.label}
          </dt>
          <dd className="flex min-w-0 flex-1 items-center gap-2">
            <Meter
              value={factor.score}
              color={trustFill(factor.score)}
              className="min-w-[28px]"
            />
            <span className="w-5 shrink-0 text-right font-mono text-body-sm text-on-surface">
              {factor.score}
            </span>
            <span
              className="w-8 shrink-0 text-right font-mono text-label-mono-xs text-outline"
              title={`Weight in the composite: ${(factor.weight * 100).toFixed(0)}%`}
            >
              {(factor.weight * 100).toFixed(0)}%
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Composite trust: the score as a swept arc, and every factor that produced it
 * as a weighted bar beside it.
 *
 * The factors are spelled out on purpose — a single number with no
 * decomposition is exactly the black box this product exists to avoid. The arc
 * length and every bar are computed from real values; nothing is a fixed shape.
 */
export function TrustGauge({
  score,
  factors,
  label = "Composite trust",
  className,
}: {
  score: number;
  factors: TrustFactor[];
  label?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-6 gap-y-4", className)}>
      <TrustDial score={score} label={label} />
      <TrustFactors factors={factors} className="min-w-[240px] flex-1" />
    </div>
  );
}
