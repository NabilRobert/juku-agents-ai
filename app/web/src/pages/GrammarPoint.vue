<script setup lang="ts">
// One sentence structure: what it means, how it's formed, notes, and examples that can be explained.
import ExampleSentence from "../components/ExampleSentence.vue";
import type { Example, SentenceBreakdown } from "../lib/types";

defineProps<{
  point: {
    grammar_id: string;
    pattern: string;
    level: number;
    meaning: string;
    formation: string;
    notes: string | null;
    examples: Example[];
  };
  breakdowns: Record<string, SentenceBreakdown>;
  copy: Record<"back" | "meaning" | "formation" | "notes" | "examples", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <p class="mb-2"><a :href="`/tata-bahasa?level=${point.level}`" class="text-sm">← {{ copy.back }}</a></p>
    <section class="card sm:p-8">
      <div class="flex items-start justify-between gap-3">
        <h1 lang="ja" class="text-4xl font-black">{{ point.pattern }}</h1>
        <span class="chip text-sm">N{{ point.level }}</span>
      </div>
      <p class="muted mt-4 text-xs font-semibold uppercase">{{ copy.meaning }}</p>
      <p class="text-lg font-medium">{{ point.meaning }}</p>
      <p class="muted mt-4 text-xs font-semibold uppercase">{{ copy.formation }}</p>
      <p lang="ja" class="mt-1 inline-block rounded-lg bg-ink px-3 py-1.5 font-mono text-lemon">{{ point.formation }}</p>
      <template v-if="point.notes">
        <p class="muted mt-4 text-xs font-semibold uppercase">{{ copy.notes }}</p>
        <p class="alert mt-1">{{ point.notes }}</p>
      </template>
    </section>
    <h2 class="section-title mt-8 mb-3">{{ copy.examples }}</h2>
    <ul class="space-y-3">
      <li v-for="example in point.examples" :key="example.ja" class="card border-l-4 border-l-amber">
        <ExampleSentence :example="example" :breakdown="breakdowns[example.ja]" />
      </li>
    </ul>
  </div>
</template>
