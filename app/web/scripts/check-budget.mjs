// FE7's budget, checked on every build (FF12's local half; Lighthouse CI is the other):
// each page's JavaScript (its island, plus the vitals island every page loads, plus
// their shared chunks) at most 100 KB compressed, and the stylesheet at most 30 KB.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const DIST = new URL("../../src/juku_app/static/dist/", import.meta.url);
const JS_BUDGET = 100 * 1024;
const CSS_BUDGET = 30 * 1024;
const manifest = JSON.parse(readFileSync(new URL(".vite/manifest.json", DIST), "utf8"));
const gzipped = (file) => gzipSync(readFileSync(new URL(file, DIST))).length;

function chunks(key, seen = new Set()) {
  if (seen.has(key)) return seen;
  seen.add(key);
  for (const imported of manifest[key]?.imports ?? []) chunks(imported, seen);
  return seen;
}

let failed = false;
const pages = { chat: ["src/islands/chat.ts"], quiz: ["src/islands/quiz.ts"], other: [] };
for (const [page, islands] of Object.entries(pages)) {
  const keys = new Set();
  for (const island of ["src/islands/vitals.ts", ...islands]) chunks(island, keys);
  const bytes = [...keys].reduce((total, key) => total + gzipped(manifest[key].file), 0);
  const ok = bytes <= JS_BUDGET;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "OVER"} ${page.padEnd(6)} JS ${(bytes / 1024).toFixed(1)} KB of ${JS_BUDGET / 1024} KB`);
}
const css = gzipped(manifest["src/styles.css"].file);
failed ||= css > CSS_BUDGET;
console.log(`${css <= CSS_BUDGET ? "ok  " : "OVER"} styles CSS ${(css / 1024).toFixed(1)} KB of ${CSS_BUDGET / 1024} KB`);
if (failed) process.exit(1);
