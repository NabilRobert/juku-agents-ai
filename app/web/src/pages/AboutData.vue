<script setup lang="ts">
// Tentang data: the attribution text, written in tentang_data.html (where a test keeps it equal to the data docs).
defineProps<{ html: string }>();
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <article class="about card mx-auto max-w-3xl space-y-3 leading-relaxed" v-html="html"></article>
</template>
