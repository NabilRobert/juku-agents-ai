<script setup lang="ts">
// Tata bahasa: a level's grammar points in teaching order, each opening its explanation.
import type { GrammarSummary } from "../lib/types";

defineProps<{ level: number; levels: number[]; points: GrammarSummary[]; copy: Record<"title" | "intro", string> }>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title">{{ copy.title }}</h1>
    <p class="muted mt-1">{{ copy.intro }}</p>
    <nav class="mt-4 mb-5 flex gap-2" aria-label="JLPT">
      <a
        v-for="choice in levels"
        :key="choice"
        :href="`/tata-bahasa?level=${choice}`"
        :aria-current="choice === level ? 'page' : undefined"
        class="rounded-full px-4 py-1.5 font-bold no-underline"
        :class="choice === level ? 'bg-ink text-lemon hover:text-lemon' : 'border border-ink/20 bg-white'"
        >N{{ choice }}</a
      >
    </nav>
    <ol class="grid gap-2 sm:grid-cols-2">
      <li v-for="(point, index) in points" :key="point.grammar_id">
        <a :href="`/tata-bahasa/${point.grammar_id}`" class="card flex h-full items-start gap-3 p-4 no-underline hover:border-orange">
          <span class="muted w-6 shrink-0 pt-1 text-right text-xs">{{ index + 1 }}</span>
          <span>
            <span lang="ja" class="block text-lg font-bold">{{ point.pattern }}</span>
            <span class="muted block">{{ point.meaning }}</span>
          </span>
        </a>
      </li>
    </ol>
  </div>
</template>
