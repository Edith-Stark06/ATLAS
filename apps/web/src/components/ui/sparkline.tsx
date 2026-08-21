const WIDTH = 100;
const HEIGHT = 40;

/** Catmull-Rom → cubic Bézier, so the line reads as a smooth trend rather
 * than a polyline. Tension 0.5 is the standard uniform variant. */
function smoothPath(points: { x: number; y: number }[]): string {
  if (points.length < 2) return "";

  let d = `M${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;

    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;

    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

/** Smoothed line + gradient area. Values are normalised to their own min/max. */
export function Sparkline({
  values,
  stroke = "var(--color-tertiary-green)",
  className,
  /** Unique per instance — SVG gradient ids are document-global. */
  gradientId = "sparkline-gradient",
  animate = true,
}: {
  values: number[];
  stroke?: string;
  className?: string;
  gradientId?: string;
  animate?: boolean;
}) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series would divide by zero; render it down the middle instead.
  const span = max - min || 1;

  const points = values.map((value, i) => ({
    x: (i / (values.length - 1)) * WIDTH,
    y: HEIGHT - ((value - min) / span) * (HEIGHT - 6) - 3,
  }));

  const line = smoothPath(points);
  const area = `${line} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`;

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.25" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        // pathLength normalises the dash to 100 units regardless of the
        // actual path length, so one keyframe works for every series.
        pathLength={animate ? 100 : undefined}
        strokeDasharray={animate ? 100 : undefined}
        strokeDashoffset={animate ? 100 : undefined}
        className={animate ? "animate-draw-line" : undefined}
      />
    </svg>
  );
}
