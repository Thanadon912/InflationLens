export type GeographyCode = "USA" | "EA";
export type WindowCode = "12m" | "1m" | "6m";
export type AdjustmentCode = "as_published" | "sa" | "nsa";

export interface DataSnapshotMeta {
  snapshot_id: string;
  sync_run_id: string;
  requested_period: string;
  actual_period: string;
  as_of: string;
  stale: boolean;
  source_vintages: string[];
}

export interface ApiMeasureRow {
  id: string;
  code: string;
  name: string;
  note?: string | null;
  seasonally_adjusted: boolean | null;
  src: string;
  yoy: number | null;
  mom: number | null;
  period: string | null;
  coverage: string;
  confidence: string;
  is_estimated: boolean;
  method: string;
  data_snapshot?: DataSnapshotMeta;
}

export interface ApiContextItem {
  k: string;
  v: number;
}

export interface MeasuresApiResponse {
  geography: string;
  window: WindowCode;
  adjustment: AdjustmentCode;
  measures: ApiMeasureRow[];
  context: ApiContextItem[];
}

export interface CategoriesApiResponse {
  geography: string;
  period: string;
  categories: Array<{ name: string; v: number; key: string }>;
}

export interface RegionTailEntry {
  region: string;
  v: number;
}

export interface RegionsUsApiResponse {
  geography: string;
  regions: Record<string, number>;
  regionTails: { lo: RegionTailEntry; hi: RegionTailEntry } | null;
  stateRegion: Record<string, string>;
  stateValues: Record<string, number>;
  stateNames: Record<string, string>;
  modelled: boolean;
}

export interface WorldCrossSectionApiResponse {
  byIso: Record<string, number>;
  headline: number | null;
  median: number | null;
  g20: number | null;
  economies: number;
  tails: Array<{ name: string; v: number }>;
}

export interface ApiPublisherItem {
  org: string;
  full: string;
  url: string;
  series: number;
  cov: string;
  latest: string | null;
  next: string | null;
}

export interface DataSourcesApiResponse {
  config_version: string;
  defaults: Record<string, number>;
  sources: Array<Record<string, unknown>>;
  publishers: ApiPublisherItem[];
}

export interface ResolveMatch {
  kind: string;
  id: GeographyCode;
  label: string;
}

export interface ResolveApiResponse {
  query: string;
  matches: ResolveMatch[];
}

/* ── Assembled Frontend Domain Models (`window.LENS`) ── */

export interface MeasureItem {
  id: string;
  code: string;
  name: string;
  yoy: number | null;
  mom: number | null;
  period: string | null;
  src: string;
  note: string;
  seasonallyAdjusted: boolean | null;
  coverage: string;
  isEstimated: boolean;
}

export interface CategoryItem {
  name: string;
  v: number;
}

export interface UsView {
  asOf: string | null;
  measures: MeasureItem[];
  spread: { lo: number; hi: number } | null;
  index: { v: string; base: string } | null;
  context: Array<{ k: string; v: string }>;
  categories: CategoryItem[];
  modelled: boolean;
  regions: Record<string, number>;
  stateRegion: Record<string, string>;
  stateValues: Record<string, number>;
  stateNames: Record<string, string>;
  regionTails: { lo: RegionTailEntry; hi: RegionTailEntry } | null;
}

export interface WorldView {
  headline: { v: number | null; label: string; period: string | null; src: string | null };
  median: { v: number | null; label: string; period: string | null; src: string | null };
  g20: { v: number | null; label: string; src: string | null };
  economies: number;
  regions: Array<{ name: string; v: number | null }>;
  tails: Array<{ name: string; v: number }>;
  byIso: Record<string, number>;
}

export interface PublisherSource {
  org: string;
  full: string;
  url: string;
  series: string;
  cov: string;
  latest: string;
  next: string;
}

export interface LensData {
  asOf: string;
  geography: GeographyCode;
  world: WorldView;
  us: UsView;
  sources: PublisherSource[];
}

export interface LoadOptions {
  window?: WindowCode;
  adjustment?: AdjustmentCode;
}

export interface LensApi {
  base: string;
  load: (geo?: GeographyCode, opts?: LoadOptions) => Promise<LensData>;
  resolve: (q: string) => Promise<ResolveMatch[]>;
}

export interface BasketWeights {
  housing: number;
  food: number;
  energy: number;
}

declare global {
  interface Window {
    LENS_API_BASE?: string;
    LENS?: LensData;
    LENS_READY?: Promise<LensData | null>;
    LENS_ERROR?: unknown;
    LENS_API?: LensApi;
  }
}
