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

## 2. Desktop Visual, Typography & Cartography Standards (Impeccable Doctrine)

- **Scroll Synchronization & Reveal**:
  - In `#showcase`, all 7 national inflation measures must be 100% visible immediately when Act 2 enters. Never use aggressive scroll-stagger formulas (`var(--rev) * 7.5 - var(--i) * 0.65`) that hide later items during normal reading positions.
- **Perspective & Cartographic Alignment**:
  - During zoom transitions between different map projections (e.g. Natural Earth world map to Albers USA state map), the camera must smoothly track and glide the focus point (`[cx, cy] -> [targetX, targetY]`) matching the exact scale ratio (`wUs / wWorld`). The cross-dissolve must happen at the exact same screen position so there is zero teleportation, double-exposure ghosting, or perspective disorientation.
- **Level of Detail (LOD) & Decluttering**:
  - When zooming closer into a regional subject, unimportant macro data (such as global latitude/longitude graticules and distant country extreme tails) must fade out early so they do not become distracting visual clutter.
- **Layout Breathing Room & Grid Integrity**:
  - Container widths for data panels must account for padding. Content width must ensure multi-column components (like the 2-column By Category ladder) have at least ~260px per column so category names, progress bars, and percentage values never collide or overlap.
- **Footnote & Disclaimer Placement**:
  - Disclaimers explaining the map (such as `"State shading is MODELLED..."`) must be positioned logically without interrupting data flow or pushing category tables off-screen.
- **Vertical Budget**:
  - The left column of Act 2 must fit within standard viewport heights (e.g. 768px – 963px) without vertical clipping or overflow.

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
