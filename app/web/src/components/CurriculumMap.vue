<script setup lang="ts">
// The whole path, N5 to the learner's target: each level's units as tiles, the current one ringed.
import type { CurriculumOverview } from "../lib/types";
import ProgressBar from "./ProgressBar.vue";
import UnitTile from "./UnitTile.vue";

type MapCopy = "title" | "unitsDone" | "unit" | "current" | "done" | "openUnit" | "placement" | "placementExplain" | "finished";

defineProps<{ curriculum: CurriculumOverview; copy: Record<MapCopy, string> }>();
</script>

<template>
  <section class="card space-y-5">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="section-title">{{ copy.title }}</h2>
        <p class="muted">
          <strong class="text-ink">{{ curriculum.units_done }}</strong> / {{ curriculum.units_total }} {{ copy.unitsDone }}
        </p>
      </div>
      <a v-if="curriculum.current_unit_id" :href="`/rencana/unit/${curriculum.current_unit_id}`" class="btn">
        {{ copy.openUnit }} →
      </a>
    </div>
    <ProgressBar :value="curriculum.units_done" :total="curriculum.units_total" />
    <p v-if="!curriculum.current_unit_id" class="alert">{{ copy.finished }}</p>
    <div v-if="curriculum.units_done === 0" class="alert flex flex-wrap items-center justify-between gap-3">
      <span>{{ copy.placementExplain }}</span>
      <a href="/rencana/penempatan" class="btn-quiet">{{ copy.placement }}</a>
    </div>
    <div v-for="level in curriculum.levels" :key="level.level">
      <h3 class="mb-2 flex items-center gap-2 font-bold">
        <span class="chip">N{{ level.level }}</span>
        <span class="muted text-xs">{{ level.units.filter((unit) => unit.status === "done").length }} / {{ level.units.length }}</span>
      </h3>
      <ol class="grid grid-cols-6 gap-1.5 sm:grid-cols-10 md:grid-cols-12">
        <li v-for="unit in level.units" :key="unit.unit_id"><UnitTile :unit="unit" :label="copy.unit" /></li>
      </ol>
    </div>
  </section>
</template>
