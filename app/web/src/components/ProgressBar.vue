<script setup lang="ts">
// A labelled bar for "so many of so many": a level's coverage, a unit's words, today's lesson.
import { computed } from "vue";

const props = defineProps<{ value: number; total: number; label?: string; tone?: "warm" | "gold" }>();
const percent = computed(() => (props.total ? Math.min(100, (100 * props.value) / props.total) : 0));
</script>

<template>
  <div>
    <div v-if="label" class="flex justify-between text-xs">
      <span>{{ label }}</span>
      <span class="font-semibold">{{ value }} / {{ total }}</span>
    </div>
    <div
      class="h-2.5 overflow-hidden rounded-full bg-ink/10"
      role="progressbar"
      :aria-valuenow="value"
      aria-valuemin="0"
      :aria-valuemax="total"
      :aria-label="label"
    >
      <div
        class="h-full rounded-full"
        :class="tone === 'gold' ? 'bg-gold' : 'bg-linear-to-r from-amber to-orange'"
        :style="{ width: `${percent}%` }"
      ></div>
    </div>
  </div>
</template>
