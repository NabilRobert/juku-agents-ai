<script setup lang="ts">
// Laporan: this week's report, written by Nikki and checked, or the facts-only fallback.
defineProps<{
  report: { week_start: string; body: string } | null;
  copy: Record<"title" | "weekOf" | "none", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title mb-4">{{ copy.title }}</h1>
    <article v-if="report" class="card">
      <p class="chip">{{ copy.weekOf }} {{ report.week_start }}</p>
      <p class="mt-3 leading-relaxed whitespace-pre-line">{{ report.body }}</p>
    </article>
    <p v-else class="alert">{{ copy.none }}</p>
  </div>
</template>
