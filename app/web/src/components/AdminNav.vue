<script setup lang="ts">
// The owner pages' title row and their links to each other and back to the owner's own learning.
defineProps<{ title: string; current: "learners" | "runs" }>();
</script>

<template>
  <div class="flex flex-wrap items-end justify-between gap-3">
    <h1 class="page-title">{{ title }}</h1>
    <p class="flex flex-wrap gap-2">
      <a href="/beranda" class="btn-quiet">Back to my own learning</a>
      <a v-if="current !== 'learners'" href="/admin/learners" class="btn-quiet">Learners</a>
      <a v-if="current !== 'runs'" href="/admin/runs" class="btn-quiet">Run Inspector</a>
    </p>
  </div>
</template>
