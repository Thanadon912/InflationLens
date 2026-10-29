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
  const prefix = v > 0 && plusSign ? "+" : "";
  return `${prefix}${v.toFixed(1)}%`;
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
