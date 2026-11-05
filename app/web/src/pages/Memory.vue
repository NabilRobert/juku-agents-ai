<script setup lang="ts">
// Shiori ingat: the page's heading, then the memory island, where each note and word can be corrected.
import MemoryIsland from "../islands/MemoryIsland.vue";
import type { KnownWord, MemoryCopy, MemoryNote } from "../islands/memory-types";
import { useCsrf } from "../lib/csrf";

defineProps<{
  notes: MemoryNote[];
  words: KnownWord[];
  knownTotal: number;
  intro: Record<"title" | "explain" | "wordsYouKnow", string>;
  copy: MemoryCopy;
}>();
const csrf = useCsrf();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title">{{ intro.title }}</h1>
    <p class="muted mt-1">{{ intro.explain }}</p>
    <p class="mt-3 mb-5"><span class="chip">{{ intro.wordsYouKnow }} {{ knownTotal }}</span></p>
    <MemoryIsland :notes="notes" :words="words" :copy="copy" :csrf="csrf" />
  </div>
</template>
