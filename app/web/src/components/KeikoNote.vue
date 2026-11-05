<script setup lang="ts">
// Keiko's weekly note on the curriculum (pipeline/run.py writes it once her plan passes the checks), or
// what's happening until there is one. Always in Indonesian, like the report.
import CitedText from "./CitedText.vue";

defineProps<{
  note: { week_start: string; body: string } | null;
  isQueued: boolean;
  copy: Record<"title" | "weekOf" | "queued" | "none", string>;
}>();
</script>

<template>
  <section class="keiko-note card border-l-4 border-l-gold space-y-2">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="section-title">📝 {{ copy.title }}</h2>
      <span v-if="note" class="chip">{{ copy.weekOf }} {{ note.week_start }}</span>
    </div>
    <CitedText v-if="note" :text="note.body" lang="id" />
    <p v-if="isQueued" class="muted text-sm" role="status">{{ copy.queued }}</p>
    <p v-else-if="!note" class="muted text-sm">{{ copy.none }}</p>
  </section>
</template>
