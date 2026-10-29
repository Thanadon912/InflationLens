import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
