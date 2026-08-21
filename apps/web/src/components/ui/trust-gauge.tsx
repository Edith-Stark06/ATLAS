import type { TrustFactor } from "@/lib/types";
import { cn } from "@/lib/utils";

const RADIUS = 45;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Where each factor's label sits around the gauge, clockwise from the top. */
const LABEL_POSITIONS = [
  "top-[-6%] left-1/2 -translate-x-1/2 flex-col",
  "top-[18%] right-[-14%] flex-col",
  "bottom-[12%] right-[-6%] flex-col-reverse",
  "bottom-[12%] left-[-6%] flex-col-reverse",
  "top-[18%] left-[-14%] flex-col",
];

const DOT_COLORS = [
  "bg-cyan-glow shadow-[0_0_8px_var(--color-cyan-glow)] ring-cyan-glow/30",
  "bg-tertiary-green shadow-[0_0_8px_var(--color-tertiary-green)] ring-tertiary-green/30",
  "bg-primary shadow-[0_0_8px_var(--color-primary)] ring-primary/30",
  "bg-cyan-glow shadow-[0_0_8px_var(--color-cyan-glow)] ring-cyan-glow/30",
  "bg-primary shadow-[0_0_8px_var(--color-primary)] ring-primary/30",
];

/** Vertex of the factor polygon, scaled by that factor's own score. */
function vertex(index: number, total: number, ratio: number) {
  const angle = (-90 + (360 / total) * index) * (Math.PI / 180);
  return {
    x: 70 + Math.cos(angle) * 45 * ratio,
    y: 70 + Math.sin(angle) * 45 * ratio,
  };
}

/**
 * The hero trust visualisation: an arc gauge that draws to the agent's score,
 * wrapped in slowly counter-rotating rings, with each contributing factor
 * plotted as a labelled point and joined into a polygon.
 *
 * The arc length and every vertex are computed from real values — nothing
 * here is a fixed decorative shape.
 */
export function TrustGauge({
  score,
  factors,
  label = "Trust Score",
  className,
}: {
  score: number;
  factors: TrustFactor[];
  label?: string;
  className?: string;
}) {
  const offset = CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, score)) / 100);
  const points = factors
    .map((factor, i) => vertex(i, factors.length, factor.score / 100))
    .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");

  return (
    <div
      className={cn(
        "relative flex size-[340px] shrink-0 items-center justify-center animate-pulse-glow",
        className,
      )}
      role="img"
      aria-label={`Trust score ${score} of 100, from ${factors.length} factors`}
    >
      {/* Counter-rotating orbit rings — depth and a sense of live monitoring. */}
      <svg className="absolute inset-0 size-full animate-spin-slow opacity-60" viewBox="0 0 100 100" aria-hidden>
        <circle
          cx="50"
          cy="50"
          r="48"
          fill="none"
          stroke="rgb(255 255 255 / 0.05)"
          strokeDasharray="2 4"
          strokeWidth="0.5"
        />
      </svg>
      <svg
        className="absolute inset-0 size-full animate-spin-slow-reverse opacity-80"
        viewBox="0 0 100 100"
        aria-hidden
      >
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="rgb(6 182 212 / 0.15)"
          strokeDasharray="10 5 2 5"
          strokeWidth="1"
        />
      </svg>

      {/* Score arc. Rotated -90° so it starts at 12 o'clock. */}
      <svg
        className="absolute inset-0 size-full -rotate-90 drop-shadow-[0_0_12px_rgb(6_182_212_/_0.6)]"
        viewBox="0 0 100 100"
        aria-hidden
      >
        <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="rgb(255 255 255 / 0.05)" strokeWidth="4" />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="var(--color-cyan-glow)"
          strokeLinecap="round"
          strokeWidth="4"
          strokeDasharray={CIRCUMFERENCE}
          // The resting value is the real score, so the arc is correct even
          // if the animation below never runs.
          strokeDashoffset={offset}
        >
          {/* SMIL rather than a CSS keyframe: the sweep endpoint differs per
              score, and a keyframe cannot take a per-element value (a
              `var()` endpoint silently fails to interpolate). SMIL takes
              `to` as a plain attribute and needs no client JavaScript. */}
          <animate
            attributeName="stroke-dashoffset"
            from={CIRCUMFERENCE}
            to={offset}
            dur="1.5s"
            begin="0.3s"
            fill="freeze"
            calcMode="spline"
            keySplines="0.16 1 0.3 1"
            keyTimes="0;1"
          />
        </circle>
      </svg>

      {/* Concentric depth rings. */}
      <div className="absolute inset-8 rounded-full border border-cyan-glow/10 bg-surface-container-low/80 shadow-[inset_0_0_30px_rgb(0_0_0_/_0.8)] backdrop-blur-md" />
      <div className="absolute inset-12 rounded-full border border-cyan-glow/20 bg-surface/90 shadow-[0_0_40px_rgb(6_182_212_/_0.15)]" />

      {/* Factor polygon. */}
      <svg
        className="pointer-events-none absolute inset-0 size-full animate-draw-radar opacity-0 [animation-delay:900ms]"
        viewBox="0 0 140 140"
        aria-hidden
      >
        <polygon
          points={points}
          fill="rgb(6 182 212 / 0.08)"
          stroke="rgb(6 182 212 / 0.5)"
          strokeLinejoin="round"
          strokeWidth="1.5"
          className="drop-shadow-[0_0_5px_rgb(6_182_212_/_0.3)]"
        />
      </svg>

      {/* Factor labels, staggered in after the arc completes. */}
      {factors.slice(0, LABEL_POSITIONS.length).map((factor, i) => (
        <div
          key={factor.key}
          className={cn(
            "absolute flex animate-draw-radar items-center gap-1 opacity-0",
            LABEL_POSITIONS[i],
          )}
          style={{ animationDelay: `${1000 + i * 100}ms` }}
        >
          <span className="whitespace-nowrap font-mono text-label-mono-xs text-white/80">
            {factor.label}
          </span>
          <span className={cn("size-2 rounded-full ring-2", DOT_COLORS[i])} />
        </div>
      ))}

      {/* Central score. */}
      <div className="relative z-10 flex size-32 flex-col items-center justify-center rounded-full border-2 border-cyan-glow/50 bg-gradient-to-b from-[#11131a] to-[#191b23] shadow-[0_0_30px_rgb(6_182_212_/_0.3),inset_0_0_15px_rgb(6_182_212_/_0.2)]">
        <span className="text-[72px] font-extrabold leading-none tracking-tighter text-white drop-shadow-[0_2px_10px_rgb(255_255_255_/_0.4)]">
          {score}
        </span>
        <span className="mt-1 font-mono text-label-mono-xs uppercase tracking-[0.2em] text-cyan-glow/80">
          {label}
        </span>
      </div>
    </div>
  );
}
