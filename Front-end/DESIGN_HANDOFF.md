# Handoff: Inflation Lens — landing + workbench

## Overview
Inflation Lens is a data product that computes inflation across every published measure at once (CPI-U, core CPI, chained CPI, PCE, core PCE, trimmed-mean PCE, PPI) and surfaces where they disagree. This bundle contains two designs:

- **Landing page** — hero + search console, a scroll-pinned two-act map showcase (line-drawn world → United States at state resolution), an engine explainer, and a full source ledger.
- **Workbench** — the working screen: search, a seven-measure spread axis, measure cards, category and state tables, a user-weighted basket recompute, and a per-screen provenance rail.

## About the architecture (React + TypeScript + Vite)
The frontend has been migrated from the initial static HTML/vanilla-JS prototype to a **React 19 + TypeScript + Vite** multi-page application (`index.html` and `app.html`) while preserving 100% of the Industry design system tokens, D3/TopoJSON technical map projections, scroll-pinned showcase variables, and Playwright E2E test contracts.

Key TypeScript modules in `src/`:
1. **`src/types/lens.ts`** — Strict TypeScript interfaces for all Backend API responses (`/measures/{geo}`, `/categories/{geo}`, `/regions/us`, `/world/cross-section`, `/meta/data-sources`, `/resolve`) and the normalized `window.LENS` frontend domain contract.
2. **`src/api/lensClient.ts`** — Typed API client (`loadLensData`, `resolveEntity`, `initializeGlobalLensBridge`) replacing the legacy `data.js`.
3. **`src/components/landing/ShowcaseStage.tsx`** — React component encapsulating the D3 (`d3-geo`) + `topojson-client` world and US state choropleth projections and the `requestAnimationFrame`-throttled scroll-progress CSS variable engine (`--a1`, `--wo`, `--uo`, `--us`, `--a2`, `--rev`), replacing the legacy `showcase.js`.
4. **`src/pages/LandingPage.tsx` & `src/pages/WorkbenchPage.tsx`** — Full React page components for the Landing Page (`index.html`) and Workbench (`app.html`), including live entity resolution, geography/window/adjustment rails, greedy row-staggered spread axis, basket reweighting, and CSV export.

## Fidelity
**High-fidelity.** Final colours, typography, spacing and interactions. Recreate pixel-accurately using the codebase's existing primitives. All values are tokens from the Industry design system (`../../styles.css`); the token list is at the end of this README.

---

## Backend integration — where to connect

Everything the pages display flows from **one file**: `data.js`, which assigns a single global `window.LENS`. Nothing else fetches data. Replace it with a typed API client and the whole surface goes live.

### `window.LENS` shape

```
LENS.asOf                     string   display date for the footer ("16 August 2026")

LENS.world.headline           { v: number, label, period, src }   global projection, act 1's big number
LENS.world.prior              { v, label, src }
LENS.world.median             { v, label, period, src }
LENS.world.g20                { v, label, src }
LENS.world.economies          number   count shown in the hero strip
LENS.world.cumulative         number   % above pre-COVID (unused on screen; keep or drop)
LENS.world.regions            [{ name, v: number|null, prev, note }]   act 1 "by region" list (nulls skipped)
LENS.world.tails              [{ name, v }]                            act 1 "the tails" list
LENS.world.byIso              { [ISO-3166 numeric]: number }            world map choropleth

LENS.us.asOf                  string
LENS.us.measures              [{ id, code, name, yoy, mom|null, period, src, note }]
                              ↑ THE core series. Drives act 2's ledger, the workbench
                                measure cards, and the spread axis. Order is display order.
LENS.us.spread                { lo, hi }
LENS.us.index                 { v: string, base: string }
LENS.us.context               [{ k, v }]
LENS.us.categories            [{ name, v }]   CPI components, 12-month %; act 2 ladder + workbench table
LENS.us.modelled              boolean         true ⇒ render the "modelled" flags
LENS.us.regions               { [censusRegion]: number }
LENS.us.stateRegion           { [FIPS 2-digit]: censusRegion }
LENS.us.stateTails            { hi: [{n,v}], lo: [{n,v}] }

LENS.sources                  [{ org, full, series, latest, next, cov, url }]
                              ↑ prints the landing's source ledger and the workbench rail
```

### The five integration points

| # | Where | File · symbol | What the backend must return |
|---|---|---|---|
| 1 | **Measures** | `data.js` → `LENS.us.measures` | One row per measure for the resolved entity + period: code, display name, `yoy`, `mom`, publisher, reference period. This is the primary endpoint. |
| 2 | **World choropleth** | `data.js` → `LENS.world.byIso` | `{ ISO numeric → annual % }`. The map joins on **ISO 3166-1 numeric**, which is what world-atlas `countries-110m` uses as feature `id`. Not ISO-2/3. |
| 3 | **State choropleth** | `showcase.js` → `stateVal(id, region)` + `LENS.us.stateRegion` | Currently a deterministic estimate from the region average. Replace `stateVal` with a lookup `{ FIPS → value }` from the engine. Join key is the **2-digit state FIPS** string (`"48"` = Texas), which is us-atlas's feature `id`. Keep the `modelled` flag wherever the value is not an official statistic. |
| 4 | **Categories** | `data.js` → `LENS.us.categories` | Component name + 12-month %. Bar widths are normalised against a hard `40` max in `showcase.js` and `maxC` in `app.html` — make that `Math.max(...)` when the range becomes dynamic. |
| 5 | **Search** | `app.html` → `#q` input handler; `index.html` → hero form | Today the hero form navigates to `app.html` and the workbench input filters rendered rows client-side. Replace with an entity-resolution endpoint: query string → `{ kind: country\|state\|metro\|category, id, label }`, then refetch (1)–(4) scoped to it. The landing hero should submit the query to the workbench route rather than a bare link. |

### Also needs backend work
- **Workbench left rail** (geography / window / adjustment) — the segmented groups currently only toggle `aria-pressed`. Each is a query parameter: `geo`, `window` (12-month · 1-month · 6-month annualised), `adjustment` (as published · SA · NSA).
- **"Your basket"** — `app.html` → `recompute()` reweights three components against a hardcoded `CV` object and lumps everything else into a `rest` bucket at 2.5%. Replace with a server-side reindex over the full component set and its published weights.
- **Export this view (CSV)** — placeholder `href="#"` in the workbench right rail.
- **Revisions** — the copy promises prior vintages are retained. There is no UI for it yet; if the engine exposes vintages, this is the obvious next screen.

### Static assets loaded from CDN
- `d3@7.9.0` and `topojson-client@3.1.0` — pinned with SRI hashes in `index.html`. Keep the pins.
- Geometry: `world-atlas@2.0.2/countries-110m.json`, `us-atlas@3.0.1/states-10m.json` (Natural Earth / US Census, public domain). Vendor these into the app's own static assets for production rather than hitting jsdelivr at runtime.

---

## Screens

### 1. Landing (`index.html`)

**Masthead** — sticky, `z-index:60`, `background: color-mix(in srgb, #f2f2f3 86%, transparent)` + `backdrop-filter: blur(14px) saturate(1.1)`, 1px bottom divider. Row: brand (Lucide-style search-plus glyph 17px in accent + wordmark, Barlow Condensed 600 / 19px / `letter-spacing:.1em` / uppercase), nav links (13px, uppercase, `.06em`, 68% ink; hidden below 880px), primary button.

**Hero** — `padding-block: 96px 72px`. Display: Barlow Condensed 600, `clamp(50px, 8.4vw, 124px)`, `line-height:.94`, `letter-spacing:.005em`, uppercase, `margin-left:-.052em` (optical left alignment). One `<span class="l">` per sentence — the line breaks are authored, not wrapped. The word "SEVEN" is `--color-accent`. Lede: Barlow 400, `clamp(16px,1.35vw,19px)/1.55`, `max-width:56ch`, 80% ink.

**Search console** — hairline frame (`1px solid color-mix(in srgb, ink 28%, transparent)`) on `--color-surface`, with four registration-cross corner marks (14px, 45% currentColor, offset `-7px`). Input: `clamp(16px,1.5vw,20px)`, `padding:18px 0`, no border, no outline. Submit: solid `--color-accent` fill, `--color-bg` text, Barlow Condensed 600 / 14px / `.1em` / uppercase; hover `--color-accent-600`, active `--color-accent-700`. Focus-within on the frame: border → accent + `0 0 0 3px accent@18%`.
Below it a scope row (four segmented buttons, `border-top` hairline, dividers between; pressed = `--color-accent-900` fill, paper text) and a "Try" chip row.

**Ticker strip** — 4-up grid, hairline top and bottom, right dividers between cells. Labels 11px uppercase `.12em` 55% ink; values Barlow Condensed 600 `clamp(26px,3vw,38px)`, tabular figures. Collapses to 2-up below 720px.

**Showcase** — see *Interactions* below.

**Engine section** — kicker + hairline rule + `clamp(32px,4vw,56px)` uppercase heading, then either three wireframe cells (default) or a five-stage pipeline. Cells: 1px divider border, 24px padding, registration marks, numbered kicker in accent. Pipeline: 5-column grid inside top/bottom hairlines, right dividers, 34px accent@55% numeral per stage.

**Source ledger** — 5-column table (Publisher / Series drawn / Coverage / Latest release / Next). Header 10.5px uppercase `.12em`, 58% ink, hairline under. Rows 13px padding-block, 8%-ink rules, `hover` 3% ink wash. Publisher cell: Condensed 600 16px uppercase over an 11.5px Barlow full-name line at 55% ink. Linearises to stacked blocks below 880px. Followed by a bordered "Known limits, stated plainly" note — **keep this text; it is the transparency commitment the product is built on.**

**Close + footer** — kicker, heading, two large buttons (`padding:15px 30px`, 15px Condensed `.1em` uppercase; one solid accent, one ghost with 28%-ink border), then a hairline footer at 12.5px / 58% ink.

**Variant switcher** — `<details id="vary">` fixed bottom-right. Four axes writing to `document.body.dataset`: `hero` (stack·split), `search` (bar·console), `showcase` (overlay·panel), `system` (cells·pipeline). **This is a review control for choosing a direction — delete it before shipping, or keep it behind a dev flag.** Ship defaults: `stack · console · panel · cells`.

### 2. Workbench (`app.html`)

Three columns: `236px | 1fr | 260px`. Left and right rails `position:sticky; top:47px`. Collapses to 2-col below 1140px (right rail becomes a full-width bottom band) and 1-col below 760px.

**Masthead** — on the `--color-accent-900` field, paper text, always-present search input (`padding:10px 12px 10px 36px`, 28%-paper border, 8%-paper fill; focus → `--color-accent-300` border).

**Left rail** — three segmented groups (Geography / Window / Adjustment) as vertical hairline-bordered button stacks, pressed = accent-900 fill; then "Your basket" with three range inputs (`accent-color: var(--color-accent)`) and a live recomputed figure tagged `est`.

**Head block** — kicker "Result · resolved from …", `clamp(30px,4vw,52px)` uppercase entity name, then a meta row (Reference / index level / base / measure count / spread).

**Spread axis** — 152px tall bordered card. Ticks at 2–5% (hairline verticals, 10.5px labels below); the 2% tick is a dashed accent line. One dot per measure at `left: (v−1.8)/(5.0−1.8)`, greedily row-staggered (32px rows) when two dots fall within 9% of each other. Dot: 11px accent square with an `--color-accent-800` border, value in Condensed 600 14px, code beneath at 9.5px uppercase.

**Measure cards** — `repeat(auto-fill, minmax(196px, 1fr))`, 12px gap. Each: hairline border (hover → accent@60%), code kicker in `--color-accent-700`, month-on-month delta top-right, 34px Condensed value, 11.5px note, 9.5px source line.

**Tables** — Category (name / bar / 12-mo) and State (name / region / 12-mo, sorted descending, tagged `modelled`). Bars: 7px track at 9% ink, accent fill. Values Condensed 600 16px tabular.

**Right rail** — provenance list for exactly what is on screen (publisher, series, release dates), then two outline buttons and a limits note.

---

## Interactions & behaviour

### The scroll showcase (the piece to port carefully)
Track `#showcase` is `400vh` on the `--color-accent-900` field; `#stage` is `position:sticky; top:0; height:100vh; overflow:hidden`. Scroll progress `p = clamp(-trackRect.top / (trackHeight - innerHeight), 0, 1)`, recomputed in a single `requestAnimationFrame`-throttled `scroll` listener. `p` is written to CSS custom properties on `#stage`; **all visual response is CSS reading those variables** — no per-element style writes. Port this pattern; it is what keeps it smooth.

| variable | mapped from `p` | drives |
|---|---|---|
| `--a1` | `1 − span(p, .30, .44)` | act 1 copy opacity + an 18px rise |
| world zoom `k` | `1 + ease(span(p, .20, .52)) × 6.2` | `transform` on `#w-zoom`, origin = the projected point of `[-98.5, 39.5]` |
| `--wo` | `1 − span(p, .32, .47)` | world layer opacity |
| `--uo` | `span(p, .34, .50)` | US layer opacity |
| `--us` | `.80 + span(p, .28, .56) × .20` | US layer scale |
| `--a2` | `span(p, .46, .56)` | act 2 copy opacity |
| `--rev` | `span(p, .56, .92)` | ledger row stagger (`opacity: clamp(0, --rev×9 − --i, 1)`) and bar growth (`width: calc(var(--w) × var(--rev))`) |

`span(p,a,b) = clamp((p−a)/(b−a), 0, 1)`; `ease` is `easeInOutQuad`. The rail progress bar is `scaleY(p)`; act dots switch at `p = .42`.

The "zoom to USA" is **two layers crossfading**, not one reprojection: the world is `d3.geoNaturalEarth1()`, the US is `d3.geoAlbersUsa()` (which is what correctly insets Alaska and Hawaii). The world layer scales up about the projected US centroid while fading out; the US layer scales `0.8 → 1` while fading in. Reprojecting continuously would be smoother in theory and much worse in practice — Mercator at world scale is unusable.

**Line draw-in**: on first arrival, each country path gets `stroke-dasharray = getTotalLength()`, `stroke-dashoffset` animated to 0 over 900ms with a `min(900, i×5)`ms stagger. Runs once (`drawn` flag).

**Flat mode** — `matchMedia('(max-width:880px)')` or `(prefers-reduced-motion: reduce)`: the pin is dropped (`#stage` becomes a static grid), both maps render as static boxes, all reveal variables are pinned to 1, and CSS `order` interleaves map → copy → map → copy. **Reduced-motion must be honoured; the whole showcase is motion.**

### Everything else
- Segmented groups toggle `aria-pressed` on click (single-select within the group).
- Workbench search filters both tables live on `input` via `tr.hidden`.
- Basket sliders recompute on `input`.
- `:focus-visible` is `2px solid var(--color-accent)` with `2px` offset, from the design system — do not override.
- Links: `--color-accent-700` default, `--color-accent-800` + underline (`text-underline-offset:3px`) on hover.

## State
| state | initial | set by |
|---|---|---|
| resolved entity | `United States` | search submit / geography rail |
| period window | `12-month` | window rail |
| adjustment | `As published` | adjustment rail |
| measure scope | `All measures` | landing scope row |
| basket weights | `{shelter:34, food:13, energy:7}` | sliders |
| scroll progress | `0` | scroll listener (transient, not app state) |
| variant axes | `stack·console·panel·cells` | review switcher (remove in production) |

## Design tokens
All from the Industry design system (`styles.css`).

**Colour** — bg `#f2f2f3` · surface `#e9e9ea` · text `#1d1f20` · accent `#5980a6` · divider `ink@16%`.
Accent ramp: `100 #eef6ff · 200 #d6ebff · 300 #b5d9fd · 400 #94bce3 · 500 #749dc4 · 600 #597ea3 · 700 #416180 · 800 #2c455d · 900 #1d2d3d`. Neutral ramp: `100 #f5f5f8 · 200 #e7e7ea · 300 #d4d4d7 · 400 #b7b7ba · 500 #98989b · 600 #7a7a7d · 700 #5d5d60 · 800 #424244 · 900 #2b2b2d`.
The showcase field is accent-900. Both choropleths shade from the accent ramp — light = low, dark = high. **No hue outside the steel accent is used anywhere; keep it that way.**

**Type** — headings Barlow Condensed 600, body Barlow 400/500/700. Tabular figures (`font-feature-settings:"tnum" 1`) on every number that sits in a column.

**Rhythm** — 24px leading unit, 12px half-step. Page gutter `--edge: clamp(20px, 5vw, 80px)`; content max-width 1280px. Spacing scale (density 0.85): `3.4 · 6.8 · 10.2 · 13.6 · 20.4 · 27.2px`.

**Radius** — 0 everywhere. Cards, figures and buttons are square-cornered line drawings with `+` registration marks at the corners; the solid accent primary button is the one filled object. Shadows: `sm 0 1px 2px ink@14%` · `md 0 3px 10px ink@16%` · `lg 0 12px 32px ink@22%` — used only on the variant switcher.

## Accessibility notes
- Contrast: accent-on-paper is a ~3.7:1 large-text value. Small accent text uses `--color-accent-700` (5.8:1). Preserve this distinction — do not "simplify" accent text to the base steel.
- Both map SVGs are `aria-hidden="true"`; every figure they encode is also present as text in the adjacent panels.
- The rail, scrim and scroll hint are decorative and `aria-hidden`.
- Segmented controls use `role="group"` + `aria-pressed`. If they become real filters, consider `role="radiogroup"`.

## Assets
No raster assets. Two inline SVG glyphs (brand mark, search) in the Lucide idiom at `stroke-width:1.5`. Map geometry is fetched public-domain TopoJSON (see above).

## Files
| file | what it is |
|---|---|
| `index.html` | the landing page — markup + all page CSS |
| `app.html` | the workbench — markup, CSS, and its own render/filter script |
| `showcase.js` | map projection, choropleth rendering, scroll-progress engine |
| `data.js` | **the data contract** — every figure on both pages |
| `ds-base.js` | loads the design system's `styles.css` + compiled bundle |
| `styles.css` | the Industry design system token + component sheet (reference) |

## Data provenance (as designed)
Figures are real published values, not placeholders: US CPI-U +3.4% and core CPI +2.5% (BLS, July 2026); PCE +3.7% and core PCE +3.3% (BEA, June 2026); trimmed-mean PCE +2.2% (Dallas Fed, June 2026); PPI final demand +4.7% (BLS, July 2026); global headline 3.6% for 2026 and a 3.3% median (IMF WEO April 2026); G20 4.0% (OECD interim, March 2026).

**One honest gap:** no statistical agency publishes state-level CPI. Every state figure in this design is a modelled estimate and is labelled as such on screen. Whatever the engine does here, keep the label.
