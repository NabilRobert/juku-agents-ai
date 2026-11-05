<script setup lang="ts">
// Kuis: the quiz island in a card; the island grades through the server.
import QuizIsland from "../islands/QuizIsland.vue";
import { useCsrf } from "../lib/csrf";
import type { QuizCopy, QuizItem } from "../lib/types";

defineProps<{ title: string; quiz: { items: QuizItem[] }; moreUrl: string; copy: QuizCopy }>();
const csrf = useCsrf();
</script>

<template>
  <div class="mx-auto max-w-2xl">
    <h1 class="page-title mb-4">{{ title }}</h1>
    <div class="card min-h-64 sm:p-8">
      <QuizIsland :quiz="quiz" :copy="copy" :csrf="csrf" :more-url="moreUrl" />
    </div>
  </div>
</template>
