// One small bundle per island, plus the shared stylesheet (ADR-024; FE2). The
// build writes hashed files and a manifest into the Python package's static
// folder; app/src/juku_app/assets.py reads the manifest to emit each page's tags.
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  base: "/static/dist/",
  build: {
    outDir: fileURLToPath(new URL("../src/juku_app/static/dist", import.meta.url)),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        styles: "src/styles.css",
        chat: "src/islands/chat.ts",
        quiz: "src/islands/quiz.ts",
        vitals: "src/islands/vitals.ts",
      },
    },
  },
  test: {
    environment: "jsdom",
  },
});
