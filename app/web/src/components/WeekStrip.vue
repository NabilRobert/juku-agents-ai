<script setup lang="ts">
// This week, Monday to Sunday (engine/week.py: week_days): each day's lesson done against its target, a ring
// that fills as the day's parts are done and ticks when they all are. Days still to come stay empty.
import type { WeekDay } from "../lib/types";

defineProps<{ week: WeekDay[]; title: string; weekdays: string[] }>();

const RING_LENGTH = 100; // the ring's path length, so a percentage is its dash length
const percent = (day: WeekDay): number => (day.target ? Math.min(100, (100 * day.done) / day.target) : 0);
const isDone = (day: WeekDay): boolean => day.target > 0 && day.done >= day.target;
</script>

<template>
  <div>
    <p class="text-xs font-semibold">{{ title }}</p>
    <ol class="mt-1 grid grid-cols-7 gap-1 text-center text-xs">
      <li v-for="(day, index) in week" :key="day.day" :class="{ 'opacity-40': day.is_future }"
        :aria-label="`${weekdays[index]}: ${day.done} / ${day.target}`">
        <span class="muted">{{ weekdays[index] }}</span>
        <svg viewBox="0 0 36 36" class="mx-auto size-8" aria-hidden="true">
          <circle cx="18" cy="18" r="15.9" fill="none" class="stroke-ink/10" stroke-width="4" />
          <circle cx="18" cy="18" r="15.9" fill="none" class="stroke-orange" stroke-width="4" stroke-linecap="round"
            :pathLength="RING_LENGTH" :stroke-dasharray="`${percent(day)} ${RING_LENGTH}`" transform="rotate(-90 18 18)" />
          <text v-if="isDone(day)" x="18" y="23" text-anchor="middle" class="fill-orange text-sm font-bold">✓</text>
        </svg>
      </li>
    </ol>
  </div>
</template>
