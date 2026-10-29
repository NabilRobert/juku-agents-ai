// The memory page's island: mounted only on /ingat, with the notes and words the server rendered.
import { createApp } from "vue";
import { pageCsrf, pageJson } from "../lib/http";
import MemoryIsland from "./MemoryIsland.vue";
import type { KnownWord, MemoryNote } from "./memory-types";

const root = document.getElementById("memory-island");
if (root) {
  const data = pageJson<{ notes: MemoryNote[]; words: KnownWord[] }>("memory-data");
  createApp(MemoryIsland, {
    notes: data.notes,
    words: data.words,
    copy: pageJson("memory-copy"),
    csrf: pageCsrf(),
  }).mount(root);
}
