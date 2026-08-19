import type { TrustFactor } from "@/lib/types";

const SIZE = 240;
const CENTER = SIZE / 2;
const MAX_RADIUS = 78;
const RINGS = [0.25, 0.5, 0.75, 1];

/** Factor i sits at angle -90° + i·(360/n), so the first point is at the top. */
function pointFor(index: number, total: number, ratio: number) {
  const angle = (-90 + (360 / total) * index) * (Math.PI / 180);
  return {
    x: CENTER + Math.cos(angle) * MAX_RADIUS * ratio,
    y: CENTER + Math.sin(angle) * MAX_RADIUS * ratio,
    angle,
  };
}

/**
 * Radar plot of the trust factors that compose an agent's score.
 * Unlike the static mock in the Stitch export, the polygon reflects real values.
 */
export function TrustRadar({
  score,
  factors,
}: {
  score: number;
  factors: TrustFactor[];
}) {
  const total = factors.length;

  const dataPoints = factors.map((factor, i) => pointFor(i, total, factor.score / 100));
  const polygon = dataPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="size-full max-h-[280px]"
      role="img"
      aria-label={`Trust score ${score} across ${total} factors`}
    >
      {RINGS.map((ratio) => (
        <circle
          key={ratio}
          cx={CENTER}
          cy={CENTER}
          r={MAX_RADIUS * ratio}
          fill="none"
          stroke="var(--color-outline-variant)"
          strokeOpacity={0.25}
          strokeWidth={1}
        />
      ))}

      {dataPoints.map((p, i) => (
        <line
          key={i}
          x1={CENTER}
          y1={CENTER}
          x2={pointFor(i, total, 1).x}
          y2={pointFor(i, total, 1).y}
          stroke="var(--color-outline-variant)"
          strokeOpacity={0.2}
          strokeWidth={1}
        />
      ))}

      <polygon
        points={polygon}
        fill="rgb(77 142 255 / 0.15)"
        stroke="rgb(77 142 255 / 0.6)"
        strokeWidth={1.5}
      />

      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={2.5} fill="var(--color-secondary)" />
      ))}

      {factors.map((factor, i) => {
        const label = pointFor(i, total, 1.22);
        const cos = Math.cos(label.angle);
        const anchor = Math.abs(cos) < 0.3 ? "middle" : cos > 0 ? "start" : "end";
        return (
          <text
            key={factor.key}
            x={label.x}
            y={label.y}
            textAnchor={anchor}
            dominantBaseline="middle"
            className="fill-on-surface-variant font-mono"
            style={{ fontSize: 8, letterSpacing: "0.03em" }}
          >
            {factor.label}
          </text>
        );
      })}

      <circle
        cx={CENTER}
        cy={CENTER}
        r={30}
        fill="var(--color-surface-container)"
        stroke="rgb(173 198 255 / 0.4)"
        strokeWidth={1}
      />
      <text
        x={CENTER}
        y={CENTER}
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-on-surface"
        style={{ fontSize: 26, fontWeight: 700 }}
      >
        {score}
      </text>
    </svg>
  );
}
