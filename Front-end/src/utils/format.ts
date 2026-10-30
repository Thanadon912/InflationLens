import type { GeographyCode, WindowCode } from "../types/lens";

export const GEO_LABELS: Record<GeographyCode, string> = {
  USA: "United States",
  EA: "Euro area",
};

export const WINDOW_LABELS: Record<WindowCode, string> = {
  "12m": "12-month",
  "1m": "1-month",
  "6m": "6-month annualised",
};

export const STEEL_RAMP = [
  "#eef6ff",
  "#d6ebff",
  "#b5d9fd",
  "#94bce3",
  "#749dc4",
  "#597ea3",
  "#416180",
  "#2c455d",
  "#1d2d3d",
] as const;

export function formatPercent(v: number | null | undefined, plusSign = true): string {
  if (v == null || Number.isNaN(v)) return "—";
  const rounded = Math.abs(v) < 0.05 ? 0 : Number(v.toFixed(1));
  const prefix = rounded > 0 && plusSign ? "+" : "";
  return `${prefix}${rounded.toFixed(1)}%`;
}

export function formatMoM(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "";
  const rounded = Math.abs(v) < 0.05 ? 0 : Number(v.toFixed(1));
  const prefix = rounded > 0 ? "+" : "";
  return `${prefix}${rounded.toFixed(1)} mo`;
}

export function formatPeriod(period: string | null | undefined): string | null {
  if (!period) return null;
  if (!/^\d{4}-\d{2}$/.test(period)) return period;
  const [y, m] = period.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatAsOf(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function safeExternalUrl(url: string | null | undefined): string {
  if (!url) return "#";
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return parsed.href;
    }
  } catch {
    return "#";
  }
  return "#";
}

export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

export function span(p: number, a: number, b: number): number {
  return clamp((p - a) / (b - a), 0, 1);
}

export function easeInOutQuad(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export function scaleForRate(v: number): string {
  return STEEL_RAMP[clamp(Math.round(((v - 1) / 6) * 8), 0, 8)];
}

export interface AxisScale {
  lo: number;
  hi: number;
  ticks: number[];
}

/** A "nice" axis range around the given values, padded so no dot sits on
 * the frame, with a tick step chosen from the span (0.1 → 2 points). */
export function buildAxisScale(values: number[]): AxisScale {
  if (values.length === 0) return { lo: 0, hi: 5, ticks: [0, 1, 2, 3, 4, 5] };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const raw = Math.max(max - min, 0.4);
  const step = [0.1, 0.25, 0.5, 1, 2, 5, 10].find((s) => raw / s <= 5) ?? 20;
  const lo = Math.floor((min - raw * 0.12) / step) * step;
  const hi = Math.ceil((max + raw * 0.12) / step) * step;
  const ticks: number[] = [];
  for (let t = lo; t <= hi + step / 2; t += step) {
    ticks.push(Number(t.toFixed(2)));
  }
  return { lo, hi, ticks };
}

export function axisPosition(v: number, scale: AxisScale): number {
  return ((v - scale.lo) / (scale.hi - scale.lo || 1)) * 100;
}

export interface AxisDot {
  id: string;
  code: string;
  v: number;
  left: number;
  row: number;
}

/** Greedy row packing: a dot moves to the first row where its label is at
 * least `minGap` percent clear of the previous label in that row. */
export function layoutAxisDots(
  items: Array<{ id: string; code: string; v: number }>,
  scale: AxisScale,
  minGap = 12
): { dots: AxisDot[]; rows: number } {
  const rowEnd: number[] = [];
  const dots = items
    .slice()
    .sort((a, b) => a.v - b.v)
    .map((m) => {
      const left = axisPosition(m.v, scale);
      let row = 0;
      while (rowEnd[row] != null && left - rowEnd[row] < minGap) row++;
      rowEnd[row] = left;
      return { ...m, left, row };
    });
  return { dots, rows: Math.max(1, rowEnd.length) };
}
