import { cn } from "@/lib/utils";

/**
 * ATLAS charts.
 *
 * Hand-rolled SVG, matching the rest of this app's dependency-free approach.
 * Every one of them is driven entirely by values passed in — there are no
 * decorative shapes here, and a chart that would not change if the data
 * changed does not belong in this file.
 *
 * The palette is the semantic one and only the semantic one: green approved,
 * amber escalated, coral blocked, violet only where the series *is* ATLAS.
 */

export const SERIES_COLORS = {
  approved: "var(--color-tertiary)",
  escalated: "var(--color-brand-amber)",
  blocked: "var(--color-error)",
  brand: "var(--color-primary)",
  neutral: "var(--color-outline)",
} as const;

export type SeriesKey = keyof typeof SERIES_COLORS;

// --- shared bits -------------------------------------------------------------

/** A key that says which colour means what. Charts are unreadable without one. */
export function ChartLegend({
  items,
  className,
}: {
  items: { label: string; color: string; value?: string }[];
  className?: string;
}) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span
            className="size-1.5 shrink-0 rounded-[2px]"
            style={{ backgroundColor: item.color }}
            aria-hidden
          />
          <span className="text-body-sm text-on-surface-variant">{item.label}</span>
          {item.value && (
            <span className="font-mono text-label-mono text-on-surface">{item.value}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

// --- stacked column chart ----------------------------------------------------

export interface StackedPoint {
  label: string;
  /** Segments, drawn bottom-up in the order given. */
  segments: { key: SeriesKey | string; value: number; color: string }[];
}

/**
 * Volume over time, split by outcome.
 *
 * Quiet periods are drawn as empty columns rather than skipped: a compressed
 * axis makes a lull look like traffic, which is the one thing an activity
 * chart must never do.
 */
export function StackedColumns({
  points,
  height = 160,
  className,
  /** Axis captions under the first/last column. */
  startLabel,
  endLabel,
}: {
  points: StackedPoint[];
  height?: number;
  className?: string;
  startLabel?: string;
  endLabel?: string;
}) {
  const totals = points.map((point) =>
    point.segments.reduce((sum, segment) => sum + segment.value, 0),
  );
  const peak = Math.max(...totals, 1);
  // Fewer columns than gridlines would make the grid the loudest thing here.
  const gridlines = [0.25, 0.5, 0.75, 1];

  return (
    <div className={className}>
      <div className="relative" style={{ height }}>
        {/* Gridlines behind the columns, labelled at the peak only. */}
        {gridlines.map((fraction) => (
          <span
            key={fraction}
            className="absolute inset-x-0 border-t border-outline-variant"
            style={{ bottom: `${fraction * 100}%` }}
            aria-hidden
          />
        ))}

        <span
          className="absolute inset-x-0 bottom-0 border-t border-outline-strong"
          aria-hidden
        />

        <div className="absolute inset-0 flex items-end gap-[3px]">
          {points.map((point, index) => {
            const total = totals[index];
            return (
              <div
                key={`${point.label}-${index}`}
                className="group relative flex h-full flex-1 flex-col justify-end"
                title={`${point.label} — ${total} decision${total === 1 ? "" : "s"}`}
              >
                {total === 0 ? (
                  <span className="h-px w-full bg-outline-variant" aria-hidden />
                ) : (
                  <span
                    className="flex w-full origin-bottom animate-grow-bar flex-col-reverse overflow-hidden rounded-[2px] transition-opacity group-hover:opacity-80"
                    style={{
                      height: `${Math.max((total / peak) * 100, 1.5)}%`,
                      animationDelay: `${Math.min(index * 12, 300)}ms`,
                    }}
                  >
                    {point.segments
                      .filter((segment) => segment.value > 0)
                      .map((segment) => (
                        <span
                          key={segment.key}
                          className="w-full"
                          style={{
                            height: `${(segment.value / total) * 100}%`,
                            backgroundColor: segment.color,
                          }}
                        />
                      ))}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <span className="absolute right-0 top-0 -translate-y-1/2 bg-surface-container px-1 font-mono text-label-mono-xs text-outline">
          {peak}
        </span>
      </div>

      {(startLabel || endLabel) && (
        <div className="mt-2 flex justify-between font-mono text-label-mono-xs text-outline">
          <span>{startLabel}</span>
          <span>{endLabel}</span>
        </div>
      )}
    </div>
  );
}

// --- line / area chart -------------------------------------------------------

const LINE_W = 240;
const LINE_H = 72;

/** Catmull-Rom → cubic Bézier, so a trend reads as a curve, not a polyline. */
function smoothPath(points: { x: number; y: number }[]): string {
  if (points.length < 2) return "";
  let d = `M${points[0].x.toFixed(2)},${points[0].y.toFixed(2)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
  }
  return d;
}

/**
 * A trend line over its own min/max, with an optional band showing the range
 * the values are scaled against — so a 2-point swing does not read as a cliff
 * without saying so.
 */
export function TrendLine({
  values,
  color = SERIES_COLORS.brand,
  className,
  gradientId,
  fill = true,
  /** Force the vertical scale, e.g. [0, 100] for a score. */
  domain,
  showDots = false,
}: {
  values: number[];
  color?: string;
  className?: string;
  /** Unique per instance — SVG gradient ids are document-global. */
  gradientId: string;
  fill?: boolean;
  domain?: [number, number];
  showDots?: boolean;
}) {
  if (values.length < 2) return null;

  const [min, max] = domain ?? [Math.min(...values), Math.max(...values)];
  const span = max - min || 1;
  const pad = 5;

  const points = values.map((value, i) => ({
    x: (i / (values.length - 1)) * LINE_W,
    y: LINE_H - ((value - min) / span) * (LINE_H - pad * 2) - pad,
  }));

  const line = smoothPath(points);
  const area = `${line} L${LINE_W},${LINE_H} L0,${LINE_H} Z`;
  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${LINE_W} ${LINE_H}`}
      preserveAspectRatio="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${gradientId})`} />}
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        // pathLength normalises the dash to 100 units regardless of the actual
        // path length, so one keyframe works for every series.
        pathLength={100}
        strokeDasharray={100}
        strokeDashoffset={100}
        className="animate-draw-line"
      />
      {showDots && (
        <circle
          cx={last.x}
          cy={last.y}
          r={2.5}
          fill={color}
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}

// --- donut -------------------------------------------------------------------

export interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

/**
 * Distribution across a handful of mutually exclusive states. Used only where
 * the parts genuinely sum to a whole — outcomes, trust bands — never as a
 * decorative ring.
 */
export function Donut({
  slices,
  size = 116,
  thickness = 12,
  centerValue,
  centerLabel,
  className,
}: {
  slices: DonutSlice[];
  size?: number;
  thickness?: number;
  centerValue?: React.ReactNode;
  centerLabel?: string;
  className?: string;
}) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;

  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={slices.map((s) => `${s.label} ${s.value}`).join(", ")}
    >
      <svg viewBox={`0 0 ${size} ${size}`} className="size-full -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-container-highest)"
          strokeWidth={thickness}
        />
        {total > 0 &&
          slices
            .filter((slice) => slice.value > 0)
            .map((slice) => {
              const fraction = slice.value / total;
              const dash = fraction * circumference;
              const element = (
                <circle
                  key={slice.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={thickness}
                  // A 1px gap between arcs so adjacent segments stay distinct
                  // without a border colour that would only work on one ground.
                  strokeDasharray={`${Math.max(dash - 1.5, 0)} ${circumference}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += dash;
              return element;
            })}
      </svg>

      {(centerValue !== undefined || centerLabel) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {centerValue !== undefined && (
            <span className="text-headline-md text-on-surface">{centerValue}</span>
          )}
          {centerLabel && <span className="eyebrow mt-0.5">{centerLabel}</span>}
        </div>
      )}
    </div>
  );
}

// --- meter -------------------------------------------------------------------

/** A single proportion as a track and a fill. The workhorse of this console. */
export function Meter({
  value,
  max = 100,
  color = "bg-primary",
  className,
  thickness = "h-1",
}: {
  value: number;
  max?: number;
  /** A Tailwind background class, so it participates in the theme. */
  color?: string;
  className?: string;
  thickness?: string;
}) {
  const percent = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      className={cn(
        "w-full overflow-hidden rounded-full bg-surface-container-highest",
        thickness,
        className,
      )}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-500", color)}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

/** Several proportions sharing one track — an outcome mix, a band split. */
export function StackedMeter({
  segments,
  className,
  thickness = "h-1.5",
}: {
  segments: { label: string; value: number; color: string }[];
  className?: string;
  thickness?: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);

  return (
    <div
      className={cn(
        "flex w-full overflow-hidden rounded-full bg-surface-container-highest",
        thickness,
        className,
      )}
    >
      {total > 0 &&
        segments
          .filter((segment) => segment.value > 0)
          .map((segment) => (
            <span
              key={segment.label}
              title={`${segment.label}: ${segment.value}`}
              style={{
                width: `${(segment.value / total) * 100}%`,
                backgroundColor: segment.color,
              }}
            />
          ))}
    </div>
  );
}
