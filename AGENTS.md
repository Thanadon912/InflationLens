# Agent Guidelines & Operational Directives (Inflation Lens)

This file defines mandatory rules and protocols for AI agents working on the **Inflation Lens** codebase.

---

## 1. Mandatory Mobile Verification Rule (Frontend Visuals)

> [!IMPORTANT]
> **Every time changes are made to frontend visuals (CSS, layouts, components, typography, responsive breakpoints, or animations), a thorough Mobile Viewport Verification is MANDATORY before completing the task.**

### 1.1 Target Mobile Viewports to Test
Agents must verify visual integrity across common real-world mobile form factors:
- **iPhone Standard**: `390 x 844` (iPhone 12 / 13 / 14 / 15)
- **Compact Mobile**: `375 x 667` (iPhone SE)
- **Android Standard**: `412 x 915` (Pixel 7 / Samsung Galaxy S23)

### 1.2 Mandatory Inspection Checklist for Mobile
Whenever frontend visual code is touched, verify the following:
1. **Zero Horizontal Overflow**:
   - `document.documentElement.scrollWidth` must strictly equal `window.innerWidth`.
   - `hasHorizontalScroll` must be `false` on all pages (`index.html`, `app.html`, etc.).
2. **No Text or Data Clipping**:
   - Headers, descriptions, data tables, and footnotes must not be clipped by the viewport boundaries.
   - Measure rows and category bars must fit comfortably within mobile margins.
   - Source publishers (`BLS`, `FRED`, `DALLAS FED`, etc.) must remain legible without causing line overflows.
3. **Compact & Touch-Friendly Controls**:
   - On the Workbench (`app.html`), controls (Geography, Window, Adjustment) must render as segmented horizontal button groups to conserve vertical space and prevent excessive scrolling.
   - Search input must adapt cleanly (e.g., wrapping to 100% width on row 2 on narrow viewports).
   - Slider controls and interactive tap targets must maintain minimum usable dimensions (>= 44x44px touch targets).
4. **Natural Mobile Document Flow**:
   - Mobile uses `body[data-flat]` where `#stage` unpins into a natural vertical document layout (`height: auto; position: static`). Maps, text, and measures must stack logically in reading order.

### 1.3 How to Run Automated Mobile Verification
Automated end-to-end visual audit tests are defined in `Front-end/e2e/visual-audit.spec.ts`.
Run:
```bash
cd Front-end
npx playwright test visual-audit
```
Inspect screenshots generated in the artifact directory (`mobile_landing_*.png`, `mobile_workbench_*.png`) to ensure visual perfection.

---

## 2. Desktop Visual, Typography & Layout Standards (Impeccable Doctrine)

- **Capabilities Studio Showcase**:
  - The Showcase features 4 interactive studio lenses:
    1. **Multi-Measure Spread**: Horizontal dot-ladder comparison across all 7 national inflation metrics with dynamic gap indicator and source annotations.
    2. **Regional Disparity**: Interactive choropleth map switching between US Census regions and Euro Area member states with real-time hover cards.
    3. **Category Drivers**: Top positive and negative category contributors with proportional deviation bars and relative weights.
    4. **Personal Basket Simulator**: Interactive spending category sliders and demographic presets (Young Renters, Commuter Family, Fixed-Income Retiree) demonstrating personal inflation divergence.
- **Scroll & Viewport Integrity**:
  - Studio lenses must maintain zero vertical clipping and zero horizontal overflow.
  - Tab navigation must be fully keyboard accessible (`role="tablist"` / `role="tab"` / arrow key navigation) with clear focus indicators.
- **Layout Breathing Room & Grid Integrity**:
  - Data containers must maintain clean padding and consistent typography hierarchy.
  - Multi-column tables and category bars must allocate sufficient width (minimum 240px per column) to prevent text clipping or wrapping of numerical percentages.
- **Footnote & Disclaimer Placement**:
  - Disclaimers explaining modeled data (e.g. `"State shading is MODELLED..."`) must remain distinct, bordered with subtle dashed borders, and never overlap interactive controls or primary charts.

---

## 3. Testing & Build Integrity

Before committing or reporting completion:
1. **TypeScript Build**:
   ```bash
   cd Front-end && npm run build
   ```
   Must succeed with zero TypeScript errors and zero lint errors.
2. **Frontend Playwright Tests**:
   ```bash
   cd Front-end && npx playwright test
   ```
   All test suites (search, measures, visual audit, navigation) must pass.
3. **Backend Pytest Suite**:
   ```bash
   cd Back-end && .venv/bin/python -m pytest
   ```
   All tests (currently 745 tests) must pass with zero failures.
