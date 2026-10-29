import type {
  CategoriesApiResponse,
  DataSourcesApiResponse,
  GeographyCode,
  LensData,
  LoadOptions,
  MeasureItem,
  MeasuresApiResponse,
  PublisherSource,
  RegionsUsApiResponse,
  ResolveApiResponse,
  ResolveMatch,
  UsView,
  WorldCrossSectionApiResponse,
  WorldView,
} from "../types/lens";
import { formatAsOf, formatPeriod, safeExternalUrl } from "../utils/format";

export const API_BASE =
  (typeof window !== "undefined" && window.LENS_API_BASE) ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:5000/api/v1";

const SRC_NAME: Record<string, string> = {
  bls: "BLS",
  bea: "BEA",
  fred: "FRED",
  eurostat: "Eurostat",
  ecb: "ECB",
  world_bank: "World Bank",
};

function srcFor(m: { id: string; src: string }): string {
  if (m.id === "trim") return "Dallas Fed";
  return SRC_NAME[m.src] || m.src || "—";
}

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: { message?: string };
    };
    throw new Error(
      `${path} -> HTTP ${res.status}: ${body.error?.message || res.statusText}`
    );
  }
  return (await res.json()) as T;
}

function assembleUs(
  measuresRes: MeasuresApiResponse,
  categoriesRes: CategoriesApiResponse | null,
  regionsRes: RegionsUsApiResponse | null
): UsView {
  const measures: MeasureItem[] = measuresRes.measures.map((m) => ({
    id: m.id,
    code: m.code,
    name: m.name,
    yoy: m.yoy,
    mom: m.mom,
    period: formatPeriod(m.period),
    src: srcFor(m),
    note: m.note || "",
    seasonallyAdjusted: m.seasonally_adjusted,
    coverage: m.coverage,
    isEstimated: m.is_estimated,
  }));

  const withValues = measures
    .filter((m): m is MeasureItem & { yoy: number } => m.yoy != null)
    .map((m) => m.yoy);
  const spread = withValues.length
    ? { lo: Math.min(...withValues), hi: Math.max(...withValues) }
    : null;
  const cpi = measures.find((m) => m.id === "cpi");

  return {
    asOf: cpi ? cpi.period : null,
    measures,
    spread,
    index: null,
    context: (measuresRes.context || []).map((c) => ({
      k: c.k,
      v: `${c.v}%`,
    })),
    categories: (categoriesRes?.categories || []).map((c) => ({
      name: c.name,
      v: c.v,
    })),
    modelled: true,
    regions: regionsRes?.regions || {},
    stateRegion: regionsRes?.stateRegion || {},
    stateValues: regionsRes?.stateValues || {},
    stateNames: regionsRes?.stateNames || {},
    regionTails: regionsRes?.regionTails || null,
  };
}

function assembleWorld(worldRes: WorldCrossSectionApiResponse): WorldView {
  return {
    headline: {
      v: worldRes.headline,
      label: "Global headline inflation",
      period: null,
      src: null,
    },
    median: {
      v: worldRes.median,
      label: "Global median",
      period: null,
      src: "World Bank",
    },
    g20: { v: worldRes.g20, label: "G20", src: null },
    economies: worldRes.economies,
    regions: [],
    tails: worldRes.tails.map((t) => ({ name: t.name, v: t.v })),
    byIso: worldRes.byIso,
  };
}

function assembleSources(sourcesRes: DataSourcesApiResponse): PublisherSource[] {
  return (sourcesRes.publishers || []).map((p) => ({
    org: p.org,
    full: p.full,
    url: safeExternalUrl(p.url),
    series: `${p.series} series drawn`,
    cov: p.cov,
    latest: p.latest ? formatAsOf(p.latest) : "—",
    next: p.next || "Not published",
  }));
}

export async function loadLensData(
  geo: GeographyCode = "USA",
  { window: win = "12m", adjustment = "as_published" }: LoadOptions = {}
): Promise<LensData> {
  const qs = `?window=${encodeURIComponent(win)}&adjustment=${encodeURIComponent(
    adjustment
  )}`;
  const [measuresRes, categoriesRes, regionsRes, worldRes, sourcesRes] =
    await Promise.all([
      fetchJSON<MeasuresApiResponse>(`/measures/${geo}${qs}`),
      fetchJSON<CategoriesApiResponse>(`/categories/${geo}`).catch(() => null),
      geo === "USA"
        ? fetchJSON<RegionsUsApiResponse>("/regions/us")
        : Promise.resolve(null),
      fetchJSON<WorldCrossSectionApiResponse>("/world/cross-section"),
      fetchJSON<DataSourcesApiResponse>("/meta/data-sources"),
    ]);

  const us = assembleUs(measuresRes, categoriesRes, regionsRes);
  const cpiSnapshot = measuresRes.measures.find(
    (m) => m.id === "cpi"
  )?.data_snapshot;

  const lens: LensData = {
    asOf: cpiSnapshot
      ? formatAsOf(cpiSnapshot.as_of)
      : formatAsOf(new Date().toISOString()),
    geography: geo,
    world: assembleWorld(worldRes),
    us,
    sources: assembleSources(sourcesRes),
  };

  if (typeof window !== "undefined") {
    window.LENS = lens;
  }
  return lens;
}

export async function resolveEntity(q: string): Promise<ResolveMatch[]> {
  if (!q || !q.trim()) return [];
  const data = await fetchJSON<ResolveApiResponse>(
    `/resolve?q=${encodeURIComponent(q.trim())}`
  );
  return data.matches;
}

export function initializeGlobalLensBridge(): Promise<LensData | null> {
  if (typeof window === "undefined") {
    return Promise.resolve(null);
  }
  document.body.dataset.apiBase = API_BASE;
  window.LENS_API = {
    base: API_BASE,
    load: loadLensData,
    resolve: resolveEntity,
  };
  if (!window.LENS_READY) {
    window.LENS_READY = loadLensData("USA").catch((err: unknown) => {
      console.error(`lensClient: could not reach the engine at ${API_BASE}`, err);
      window.LENS_ERROR = err;
      document.body.setAttribute("data-lens", "unavailable");
      return null;
    });
  }
  return window.LENS_READY;
}
