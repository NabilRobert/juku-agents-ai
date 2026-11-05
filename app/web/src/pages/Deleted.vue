<script setup lang="ts">
// Shown once, after a learner deletes their data.
defineProps<{ copy: Record<"title" | "explain", string> }>();
</script>

<template>
  <section class="card mx-auto mt-6 max-w-3xl">
    <h1 class="page-title">{{ copy.title }}</h1>
    <p class="mt-2">{{ copy.explain }}</p>
  </section>
</template>
