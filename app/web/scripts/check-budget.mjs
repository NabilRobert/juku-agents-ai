// FE7's budget, checked on every build (FF12's local half; Lighthouse CI is the other):
// each page's JavaScript (the app entry and the vitals script every page loads, the page's
// own component chunk, and their shared chunks) at most 100 KB compressed, and the
// stylesheet at most 30 KB.
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
const pages = Object.keys(manifest).filter((key) => key.startsWith("src/pages/"));
if (pages.length === 0) throw new Error("no page components in the build: is src/main.ts an entry in vite.config.ts?");
for (const page of pages) {
  const keys = new Set();
  for (const entry of ["src/islands/vitals.ts", "src/main.ts", page]) chunks(entry, keys);
  const bytes = [...keys].reduce((total, key) => total + gzipped(manifest[key].file), 0);
  const ok = bytes <= JS_BUDGET;
  failed ||= !ok;
  const name = page.slice("src/pages/".length, -".vue".length);
  console.log(`${ok ? "ok  " : "OVER"} ${name.padEnd(13)} JS ${(bytes / 1024).toFixed(1)} KB of ${JS_BUDGET / 1024} KB`);
}
const css = gzipped(manifest["src/styles.css"].file);
failed ||= css > CSS_BUDGET;
console.log(`${css <= CSS_BUDGET ? "ok  " : "OVER"} styles CSS ${(css / 1024).toFixed(1)} KB of ${CSS_BUDGET / 1024} KB`);
if (failed) process.exit(1);
