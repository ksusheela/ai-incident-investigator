import { useId, useState } from "react";

export interface BarChartDatum {
  label: string;
  value: number;
  /** CSS custom property name (see `.viz-root` in `styles/custom.css`) carrying this bar's color. */
  colorVar: string;
}

interface BarChartProps {
  data: BarChartDatum[];
  maxValue: number;
  valueFormatter?: (value: number) => string;
  ariaLabel: string;
}

const BAND_WIDTH = 84;
const BAR_WIDTH = 24;
const CHART_HEIGHT = 200;
const TOP_MARGIN = 24;
const BOTTOM_MARGIN = 28;
const PLOT_HEIGHT = CHART_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN;

/** A rect path rounded on its top two corners only, square at the baseline. */
function roundedTopRectPath(x: number, y: number, width: number, height: number, radius: number): string {
  if (height <= 0) return "";
  const r = Math.min(radius, height / 2, width / 2);
  return (
    `M${x + r},${y} H${x + width - r} A${r},${r} 0 0 1 ${x + width},${y + r} ` +
    `V${y + height} H${x} V${y + r} A${r},${r} 0 0 1 ${x + r},${y} Z`
  );
}

/**
 * A single-series bar chart built to the "dataviz" skill's mark spec:
 * thin bars (<=24px) with a 4px rounded top / square baseline, a
 * recessive hairline baseline, direct value + category labels on every
 * bar (so nothing is gated behind hover), and a per-bar hover/focus
 * tooltip. No legend box — a single series needs none; the chart's own
 * title names what's plotted. Colors come from CSS custom properties so
 * they follow the app's `data-bs-theme` light/dark toggle automatically.
 */
export function BarChart({ data, maxValue, valueFormatter = String, ariaLabel }: BarChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const titleId = useId();
  const width = data.length * BAND_WIDTH;
  const baselineY = TOP_MARGIN + PLOT_HEIGHT;
  const active = activeIndex === null ? null : data[activeIndex];

  return (
    <div className="viz-root">
      <div className="viz-tooltip small text-secondary mb-1" aria-hidden="true">
        {active ? `${active.label}: ${valueFormatter(active.value)}` : " "}
      </div>
      <svg
        viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
        role="img"
        aria-labelledby={titleId}
        className="w-100"
        style={{ maxWidth: `${width}px`, height: `${CHART_HEIGHT}px` }}
      >
        <title id={titleId}>{ariaLabel}</title>
        <line x1={0} y1={baselineY} x2={width} y2={baselineY} className="viz-baseline" />
        {data.map((datum, index) => {
          const barHeight = maxValue > 0 ? (Math.max(datum.value, 0) / maxValue) * PLOT_HEIGHT : 0;
          const bandX = index * BAND_WIDTH;
          const barX = bandX + (BAND_WIDTH - BAR_WIDTH) / 2;
          const barY = baselineY - barHeight;

          return (
            <g
              key={datum.label}
              tabIndex={0}
              role="button"
              aria-label={`${datum.label}: ${valueFormatter(datum.value)}`}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
              onFocus={() => setActiveIndex(index)}
              onBlur={() => setActiveIndex(null)}
              style={{ cursor: "pointer" }}
            >
              <rect x={bandX} y={TOP_MARGIN} width={BAND_WIDTH} height={PLOT_HEIGHT} fill="transparent" />
              <path
                d={roundedTopRectPath(barX, barY, BAR_WIDTH, barHeight, 4)}
                fill={`var(${datum.colorVar})`}
                opacity={index === activeIndex ? 0.85 : 1}
              />
              <text x={bandX + BAND_WIDTH / 2} y={barY - 6} textAnchor="middle" className="viz-value-label">
                {valueFormatter(datum.value)}
              </text>
              <text
                x={bandX + BAND_WIDTH / 2}
                y={baselineY + 18}
                textAnchor="middle"
                className="viz-axis-label"
              >
                {datum.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
