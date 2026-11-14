import type { GeographyCode, WindowCode } from "../types/lens";

export const GEO_LABELS: Record<GeographyCode, string> = {
  USA: "United States",
  EA: "Euro area",
  ABW: "Aruba",
  AFG: "Afghanistan",
  AGO: "Angola",
  AIA: "Anguilla",
  ALA: "Aland Islands",
  ALB: "Albania",
  AND: "Andorra",
  ARE: "United Arab Emirates",
  ARG: "Argentina",
  ARM: "Armenia",
  ASM: "American Samoa",
  ATA: "Antarctica",
  ATG: "Antigua and Barbuda",
  AUS: "Australia",
  AUT: "Austria",
  AZE: "Azerbaijan",
  BDI: "Burundi",
  BEL: "Belgium",
  BEN: "Benin",
  BFA: "Burkina Faso",
  BGD: "Bangladesh",
  BGR: "Bulgaria",
  BHR: "Bahrain",
  BHS: "Bahamas",
  BIH: "Bosnia and Herzegovina",
  BLR: "Belarus",
  BLZ: "Belize",
  BMU: "Bermuda",
  BOL: "Bolivia",
  BRA: "Brazil",
  BRB: "Barbados",
  BRN: "Brunei Darussalam",
  BTN: "Bhutan",
  BWA: "Botswana",
  CAF: "Central African Republic",
  CAN: "Canada",
  CHE: "Switzerland",
  CHL: "Chile",
  CHN: "China",
  CIV: "Cote d'Ivoire",
  CMR: "Cameroon",
  COD: "DR Congo",
  COG: "Republic of the Congo",
  COL: "Colombia",
  COM: "Comoros",
  CPV: "Cabo Verde",
  CRI: "Costa Rica",
  CUB: "Cuba",
  CUW: "Curacao",
  CYM: "Cayman Islands",
  CYP: "Cyprus",
  CZE: "Czechia",
  DEU: "Germany",
  DJI: "Djibouti",
  DMA: "Dominica",
  DNK: "Denmark",
  DOM: "Dominican Republic",
  DZA: "Algeria",
  ECU: "Ecuador",
  EGY: "Egypt",
  ERI: "Eritrea",
  ESP: "Spain",
  EST: "Estonia",
  ETH: "Ethiopia",
  FIN: "Finland",
  FJI: "Fiji",
  FRA: "France",
  FRO: "Faroe Islands",
  FSM: "Micronesia",
  GAB: "Gabon",
  GBR: "United Kingdom",
  GEO: "Georgia",
  GHA: "Ghana",
  GIB: "Gibraltar",
  GIN: "Guinea",
  GLP: "Guadeloupe",
  GMB: "Gambia",
  GNB: "Guinea-Bissau",
  GNQ: "Equatorial Guinea",
  GRC: "Greece",
  GRD: "Grenada",
  GRL: "Greenland",
  GTM: "Guatemala",
  GUF: "French Guiana",
  GUM: "Guam",
  GUY: "Guyana",
  HKG: "Hong Kong",
  HND: "Honduras",
  HRV: "Croatia",
  HTI: "Haiti",
  HUN: "Hungary",
  IDN: "Indonesia",
  IMN: "Isle of Man",
  IND: "India",
  IRL: "Ireland",
  IRN: "Iran",
  IRQ: "Iraq",
  ISL: "Iceland",
  ISR: "Israel",
  ITA: "Italy",
  JAM: "Jamaica",
  JOR: "Jordan",
  JPN: "Japan",
  KAZ: "Kazakhstan",
  KEN: "Kenya",
  KGZ: "Kyrgyz Republic",
  KHM: "Cambodia",
  KIR: "Kiribati",
  KOR: "South Korea",
  KWT: "Kuwait",
  LAO: "Lao PDR",
  LBN: "Lebanon",
  LBR: "Liberia",
  LBY: "Libya",
  LIE: "Liechtenstein",
  LKA: "Sri Lanka",
  LSO: "Lesotho",
  LTU: "Lithuania",
  LUX: "Luxembourg",
  LVA: "Latvia",
  MAC: "Macao",
  MAR: "Morocco",
  MCO: "Monaco",
  MDA: "Moldova",
  MDG: "Madagascar",
  MDV: "Maldives",
  MEX: "Mexico",
  MHL: "Marshall Islands",
  MKD: "North Macedonia",
  MLI: "Mali",
  MLT: "Malta",
  MMR: "Myanmar",
  MNE: "Montenegro",
  MNG: "Mongolia",
  MNP: "Northern Mariana Islands",
  MOZ: "Mozambique",
  MRT: "Mauritania",
  MSR: "Montserrat",
  MTQ: "Martinique",
  MUS: "Mauritius",
  MWI: "Malawi",
  MYS: "Malaysia",
  MYT: "Mayotte",
  NAM: "Namibia",
  NCL: "New Caledonia",
  NER: "Niger",
  NGA: "Nigeria",
  NIC: "Nicaragua",
  NLD: "Netherlands",
  NOR: "Norway",
  NPL: "Nepal",
  NRU: "Nauru",
  NZL: "New Zealand",
  OMN: "Oman",
  PAK: "Pakistan",
  PAN: "Panama",
  PER: "Peru",
  PHL: "Philippines",
  PLW: "Palau",
  PNG: "Papua New Guinea",
  POL: "Poland",
  PRI: "Puerto Rico",
  PRK: "North Korea",
  PRT: "Portugal",
  PRY: "Paraguay",
  PSE: "Palestine",
  PYF: "French Polynesia",
  QAT: "Qatar",
  ROU: "Romania",
  RUS: "Russian Federation",
  RWA: "Rwanda",
  SAU: "Saudi Arabia",
  SDN: "Sudan",
  SEN: "Senegal",
  SGP: "Singapore",
  SLB: "Solomon Islands",
  SLE: "Sierra Leone",
  SLV: "El Salvador",
  SMR: "San Marino",
  SOM: "Somalia",
  SRB: "Serbia",
  SSD: "South Sudan",
  STP: "Sao Tome and Principe",
  SUR: "Suriname",
  SVK: "Slovakia",
  SVN: "Slovenia",
  SWE: "Sweden",
  SWZ: "Eswatini",
  SXM: "Sint Maarten",
  SYC: "Seychelles",
  SYR: "Syrian Arab Republic",
  TCA: "Turks and Caicos Islands",
  TCD: "Chad",
  TGO: "Togo",
  THA: "Thailand",
  TJK: "Tajikistan",
  TKM: "Turkmenistan",
  TLS: "Timor-Leste",
  TON: "Tonga",
  TTO: "Trinidad and Tobago",
  TUN: "Tunisia",
  TUR: "Turkiye",
  TUV: "Tuvalu",
  TWN: "Taiwan",
  TZA: "Tanzania",
  UGA: "Uganda",
  UKR: "Ukraine",
  URY: "Uruguay",
  UZB: "Uzbekistan",
  VEN: "Venezuela",
  VGB: "British Virgin Islands",
  VIR: "U.S. Virgin Islands",
  VNM: "Vietnam",
  VUT: "Vanuatu",
  WSM: "Samoa",
  XKX: "Kosovo",
  YEM: "Yemen",
  ZAF: "South Africa",
  ZMB: "Zambia",
  ZWE: "Zimbabwe",
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
