import { StrictMode } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { API_BASE, loadLensData, resolveEntity } from "./api/lensClient";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import type { GeographyCode, LensData } from "./types/lens";
import "./styles/design-system.css";
import "./styles/workbench.css";

document.body.dataset.apiBase = API_BASE;
window.LENS_API = {
  base: API_BASE,
  load: loadLensData,
  resolve: resolveEntity,
};

const presetQuery = new URLSearchParams(window.location.search).get("q") || "";
let initialGeo: GeographyCode = "USA";
let initialLens: LensData | null = null;
let initialStale = false;
let initialAlertMessage: string | null = null;
let initialUnsupportedQuery: string | null = null;

const bootPromise = (async (): Promise<LensData | null> => {
  try {
    if (presetQuery) {
      const matches = await resolveEntity(presetQuery);
      if (matches.length > 0) {
        initialGeo = matches[0].id;
      } else {
        // Query specified a geography not in the 222 configured profiles
        document.body.setAttribute("data-lens", "unavailable");
        initialAlertMessage = `“${presetQuery}” could not be resolved to any of the 222 configured country profiles.`;
        initialStale = true;
        initialLens = null;
        initialUnsupportedQuery = presetQuery;
        return null;
      }
    }
    initialLens = await loadLensData(initialGeo, {
      window: "12m",
      adjustment: "as_published",
    });
    document.body.removeAttribute("data-lens");
    return initialLens;
  } catch (err) {
    console.error(`main-workbench: could not reach the engine at ${API_BASE}`, err);
    window.LENS_ERROR = err;
    document.body.setAttribute("data-lens", "unavailable");
    initialStale = true;
    initialAlertMessage =
      "The engine could not be reached. Figures on this screen may be stale or empty.";
    return null;
  }
})();

window.LENS_READY = bootPromise;
await bootPromise;

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing #root mount element in app.html");
}

const root = createRoot(rootEl);
flushSync(() => {
  root.render(
    <StrictMode>
      <WorkbenchPage
        initialGeo={initialGeo}
        initialQuery={presetQuery}
        initialLens={initialLens}
        initialStale={initialStale}
        initialAlertMessage={initialAlertMessage}
        initialUnsupportedQuery={initialUnsupportedQuery}
      />
    </StrictMode>
  );
});

// Dismiss preloader once React has rendered the workbench page
const loader = document.getElementById("page-loader");
if (loader) {
  loader.classList.add("fade-out");
  setTimeout(() => loader.remove(), 400);
}
