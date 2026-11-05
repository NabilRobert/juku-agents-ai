<script setup lang="ts">
// An agent's checked text (Nikki's report, Keiko's note) with its citations, [ref:<id>], shown as small
// marks instead of raw brackets: the checks already proved each one names a fact.
import { computed } from "vue";

const props = defineProps<{ text: string }>();
const CITATION = /\[ref:([^\]\s]+)\]/g;
const parts = computed(() =>
  props.text.split(CITATION).map((part, index) => ({ isCitation: index % 2 === 1, value: part })),
);
</script>

<template>
  <p class="leading-relaxed whitespace-pre-line">
    <template v-for="(part, index) in parts" :key="index">
      <sup v-if="part.isCitation" class="cite ml-0.5 rounded bg-lemon/70 px-1 text-[0.65rem] text-ink/70">{{ part.value }}</sup>
      <template v-else>{{ part.value }}</template>
    </template>
  </p>
</template>
