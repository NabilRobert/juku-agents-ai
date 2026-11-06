<script setup lang="ts">
// Rencana: the curriculum (Arthur, 2026-11-05: "give me a plan i can follow") and Keiko's weekly note on it,
// then coverage per level and the pace to the exam (the planner's numbers, unchanged).
import CurriculumMap from "../components/CurriculumMap.vue";
import KeikoNote from "../components/KeikoNote.vue";
import ProgressBar from "../components/ProgressBar.vue";
import type { CurriculumOverview, Progress } from "../lib/types";

defineProps<{
  progress: Progress;
  plan: { words_per_week: number | null; weeks_left: number | null; formula: string };
  curriculum: CurriculumOverview;
  curriculumCopy: InstanceType<typeof CurriculumMap>["$props"]["copy"];
  keikoNote: InstanceType<typeof KeikoNote>["$props"]["note"];
  isCheckQueued: boolean;
  keikoCopy: InstanceType<typeof KeikoNote>["$props"]["copy"];
  copy: Record<
    "title" | "wordsYouKnow" | "words" | "level" | "wordsHeading" | "kanji" | "pace" | "perWeek" | "weeks",
    string
  >;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-4">
    <div>
      <h1 class="page-title">{{ copy.title }}</h1>
      <p class="mt-1">
        {{ copy.wordsYouKnow }}: <strong class="text-xl">{{ progress.known_words }}</strong> {{ copy.words }}
      </p>
    </div>

    <CurriculumMap :curriculum="curriculum" :copy="curriculumCopy" />

    <KeikoNote :note="keikoNote" :is-queued="isCheckQueued" :copy="keikoCopy" />

    <section class="card border-l-4 border-l-orange">
      <h2 class="section-title">{{ copy.pace }}</h2>
      <p v-if="plan.words_per_week !== null" class="mt-1">
        <strong class="text-3xl font-black">{{ plan.words_per_week }}</strong> {{ copy.perWeek }} ({{ plan.weeks_left }}
        {{ copy.weeks }}).
      </p>
      <p class="muted mt-1">{{ plan.formula }}</p>
    </section>

    <section class="card space-y-4" :aria-label="copy.level">
      <div v-for="level in progress.levels" :key="level.level_name" class="grid grid-cols-[3rem_1fr] items-center gap-x-3 gap-y-1">
        <span class="chip row-span-2 justify-center">{{ level.level_name }}</span>
        <ProgressBar :value="level.words_known" :total="level.words_total" :label="copy.wordsHeading" />
        <ProgressBar :value="level.kanji_known" :total="level.kanji_total" :label="copy.kanji" tone="gold" />
      </div>
    </section>
  </div>
</template>
