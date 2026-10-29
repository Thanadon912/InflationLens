import { StrictMode } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { initializeGlobalLensBridge } from "./api/lensClient";
import { LandingPage } from "./pages/LandingPage";
import "./styles/design-system.css";
import "./styles/landing.css";

const initialLens = await initializeGlobalLensBridge();

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing #root mount element in index.html");
}

const root = createRoot(rootEl);
flushSync(() => {
  root.render(
    <StrictMode>
      <LandingPage
        initialLens={initialLens}
        initialUnavailable={initialLens === null}
      />
    </StrictMode>
  );
});
