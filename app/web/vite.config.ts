// One app entry that loads each page's component as its own chunk, the vitals script, and the shared
// stylesheet (ADR-024, revised 2026-11-05; FE2). The build writes hashed files and a manifest into the
// Python package's static folder; app/src/juku_app/assets.py reads the manifest to emit each page's tags.
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  base: "/static/dist/",
  build: {
    // Relative to this folder: into the Python package, where the app serves /static/.
    outDir: "../src/juku_app/static/dist",
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        styles: "src/styles.css",
        main: "src/main.ts",
        vitals: "src/islands/vitals.ts",
      },
    },
  },
  test: {
    environment: "jsdom",
  },
});
