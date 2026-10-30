# Inflation Lens — Front End

React 19 + TypeScript + Vite frontend for the Inflation Lens engine. It consists of two primary surfaces built with the custom Industry design system, SVG choropleth maps (`d3-geo` + `topojson-client`), and a zero-dependency responsive architecture.

## Surfaces

1. **Landing Page (`index.html` / `src/pages/LandingPage.tsx`)**
   - Hero search console with live entity resolution (`/api/v1/resolve`).
   - Two-act scrollytelling showcase:
     - **Act 1:** World choropleth projection with global headline rate and benchmark economies.
     - **Act 2:** United States state-level choropleth with 7-measure inflation spread and category ladder.
   - **Mobile Flat Mode:** On mobile devices (`<= 880px`) or `prefers-reduced-motion: reduce`, the showcase gracefully drops scroll-pinning into a cleanly stacked natural reading flow with full map visibility and category ladders.
   - Engine architectural pipeline and full official data source ledger.

2. **Workbench (`app.html` / `src/pages/WorkbenchPage.tsx`)**
   - Three-column responsive workspace:
     - **Left Rail:** Geography (`USA` / `EA`), Window (`12m` / `1m` / `6m`), Seasonal Adjustment (`as_published` / `sa`), and interactive user-basket reweighting sliders.
     - **Main Pane:** Dynamic multi-measure spread axis with greedy row-staggered dot packing (`layoutAxisDots`) to prevent label collisions on both desktop and mobile, live measure cards, and scrollable state/category breakdown tables.
     - **Right Rail:** Provenance and methodology ledger for active figures on screen, plus one-click CSV export.

## Development

```bash
# Install dependencies
npm install

# Run with Docker Compose (serves on http://localhost:3000 via Nginx)
docker compose up frontend

# Manual development server (port 3000)
npm install
npm run dev

# Typecheck and build production bundle into dist/
npm run build

# Preview production build locally
npm run preview
```

By default, the frontend expects the backend API at `http://localhost:5000/api/v1`. To point to another endpoint (e.g. during preview or testing), set `VITE_API_BASE_URL`:

```bash
VITE_API_BASE_URL=http://localhost:5055/api/v1 npm run build
```

## Testing

End-to-end tests are written in [Playwright](https://playwright.dev) under `e2e/`:

```bash
# Run all 26 E2E tests (automatically launches backend test server if not running)
npx playwright test
```

The E2E suite verifies:
- API response contract conformance (`assembleUs`, `assembleWorld`, `assembleSources`).
- Live entity search and query string handoff (`?q=...`).
- Stale state handling and accessible alert banners when the API is unreachable.
- Dynamic axis bounds on all 3 observation windows without dot clipping.
- Geography-filtered source rails and live category basket reweighting.
