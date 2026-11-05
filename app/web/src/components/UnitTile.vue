<script setup lang="ts">
// One unit on the curriculum map: its number, how far along it is, and whether it's done, current or later.
import type { UnitStatus } from "../lib/types";

defineProps<{ unit: UnitStatus; label: string }>();

function look(status: UnitStatus["status"]): string {
  if (status === "done") return "bg-gold text-ink border-gold";
  if (status === "current") return "bg-ink text-lemon border-ink ring-4 ring-amber/50";
  return "bg-white text-ink/60 border-ink/15 hover:border-orange";
}
</script>

<template>
  <a
    :href="`/rencana/unit/${unit.unit_id}`"
    class="unit-tile flex aspect-square flex-col items-center justify-center rounded-xl border-2 text-center no-underline transition"
    :class="look(unit.status)"
    :aria-current="unit.status === 'current' ? 'step' : undefined"
    :title="`${label} ${unit.number}: ${unit.words_known}/${unit.words_total}`"
  >
    <span class="text-lg leading-none font-black">{{ unit.number }}</span>
    <span v-if="unit.status === 'done'" class="text-xs" aria-hidden="true">✓</span>
    <span v-else class="text-[0.6rem] opacity-80">{{ unit.words_known }}/{{ unit.words_total }}</span>
  </a>
</template>
