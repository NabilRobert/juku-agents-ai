<script setup lang="ts">
// Rencana: coverage per level as bars, and the pace to the exam (the planner's numbers, unchanged).
import type { Progress } from "../lib/types";

defineProps<{
  progress: Progress;
  plan: { words_per_week: number | null; weeks_left: number | null; formula: string };
  copy: Record<
    "title" | "wordsYouKnow" | "words" | "level" | "wordsHeading" | "kanji" | "pace" | "perWeek" | "weeks",
    string
  >;
}>();

function share(known: number, total: number): string {
  return total ? `${(100 * known) / total}%` : "0%";
}
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title">{{ copy.title }}</h1>
    <p class="mt-1 mb-5">
      {{ copy.wordsYouKnow }}: <strong class="text-xl">{{ progress.known_words }}</strong> {{ copy.words }}
    </p>

    <section class="card space-y-4" :aria-label="copy.level">
      <div
        v-for="level in progress.levels"
        :key="level.level_name"
        class="grid grid-cols-[3rem_1fr] items-center gap-x-3 gap-y-1"
      >
        <span class="chip row-span-2 justify-center">{{ level.level_name }}</span>
        <div>
          <div class="flex justify-between text-xs">
            <span>{{ copy.wordsHeading }}</span>
            <span class="font-semibold">{{ level.words_known }} / {{ level.words_total }}</span>
          </div>
          <div class="h-2.5 overflow-hidden rounded-full bg-ink/10">
            <div class="h-full rounded-full bg-linear-to-r from-amber to-orange" :style="{ width: share(level.words_known, level.words_total) }"></div>
          </div>
        </div>
        <div>
          <div class="flex justify-between text-xs">
            <span>{{ copy.kanji }}</span>
            <span class="font-semibold">{{ level.kanji_known }} / {{ level.kanji_total }}</span>
          </div>
          <div class="h-2.5 overflow-hidden rounded-full bg-ink/10">
            <div class="h-full rounded-full bg-gold" :style="{ width: share(level.kanji_known, level.kanji_total) }"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="card mt-4 border-l-4 border-l-orange">
      <h2 class="section-title">{{ copy.pace }}</h2>
      <p v-if="plan.words_per_week !== null" class="mt-1">
        <strong class="text-3xl font-black">{{ plan.words_per_week }}</strong> {{ copy.perWeek }} ({{ plan.weeks_left }}
        {{ copy.weeks }}).
      </p>
      <p class="muted mt-1">{{ plan.formula }}</p>
    </section>
  </div>
</template>
