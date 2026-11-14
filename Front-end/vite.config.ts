import type { IncomingMessage, ServerResponse } from "node:http";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Rewrites clean extensionless routes (/workbench, /app, /home, /landing)
 * to their underlying MPA HTML entrypoints so `.html` filenames never need
 * to appear in browser URLs during local dev or preview.
 */
function cleanUrlsMiddleware(
  req: IncomingMessage,
  _res: ServerResponse,
  next: () => void,
): void {
  if (!req.url) {
    next();
    return;
  }
  const [pathname, search = ""] = req.url.split("?");
  const qs = search ? `?${search}` : "";
  if (
    pathname === "/workbench" ||
    pathname === "/workbench/" ||
    pathname === "/app" ||
    pathname === "/app/"
  ) {
    req.url = `/app.html${qs}`;
  } else if (
    pathname === "/home" ||
    pathname === "/home/" ||
    pathname === "/landing" ||
    pathname === "/landing/"
  ) {
    req.url = `/index.html${qs}`;
  }
  next();
}

const cleanUrlsPlugin: Plugin = {
  name: "inflation-lens-clean-urls",
  configureServer(server) {
    server.middlewares.use(cleanUrlsMiddleware);
  },
  configurePreviewServer(server) {
    server.middlewares.use(cleanUrlsMiddleware);
  },
};

export default defineConfig({
  plugins: [cleanUrlsPlugin, react()],
  server: {
    port: 3000,
    strictPort: true,
    watch: {
      usePolling: true,
      interval: 500,
      ignored: ["**/node_modules/**", "**/dist/**", "**/test-results/**", "**/playwright-report/**"],
    },
  },
  preview: {
    port: 3000,
    strictPort: true,
  },
  build: {
    target: "es2022",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        workbench: resolve(__dirname, "app.html"),
      },
    },
  },
});
