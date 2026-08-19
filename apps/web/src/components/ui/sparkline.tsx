const WIDTH = 100;
const HEIGHT = 30;

/** Line + area sparkline. Values are normalised to their own min/max. */
export function Sparkline({
  values,
  stroke = "var(--color-tertiary)",
  className,
}: {
  values: number[];
  stroke?: string;
  className?: string;
}) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  // Flat series would divide by zero; render it down the middle instead.
  const span = max - min || 1;

  const points = values.map((value, i) => {
    const x = (i / (values.length - 1)) * WIDTH;
    const y = HEIGHT - ((value - min) / span) * (HEIGHT - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const line = `M${points.join(" L")}`;
  const area = `${line} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`;

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      className={className}
      aria-hidden
    >
      <path d={area} fill={stroke} fillOpacity={0.12} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
