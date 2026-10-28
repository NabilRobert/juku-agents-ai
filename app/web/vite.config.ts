// One small bundle per island, plus the shared stylesheet (ADR-024; FE2). The
// build writes hashed files and a manifest into the Python package's static
// folder; app/src/juku_app/assets.py reads the manifest to emit each page's tags.
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
        chat: "src/islands/chat.ts",
        quiz: "src/islands/quiz.ts",
        memory: "src/islands/memory.ts",
        vitals: "src/islands/vitals.ts",
      },
    },
  },
  test: {
    environment: "jsdom",
  },
});
