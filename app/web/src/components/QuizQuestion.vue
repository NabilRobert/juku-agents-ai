<script setup lang="ts">
// One multiple-choice question: the prompt and its options. After an answer, the right option is yellow and a
// wrong pick struck out (`correct` given); a test that doesn't reveal answers just marks the pick (`chosen`).
import type { QuizItem } from "../lib/types";

const props = defineProps<{ item: QuizItem; chosen?: string | null; correct?: string | null; locked?: boolean }>();
defineEmits<{ choose: [option: string] }>();

function optionLook(option: string): string {
  if (props.correct) {
    if (option === props.correct) return "border-gold bg-lemon font-bold";
    if (option === props.chosen) return "border-ink/15 bg-ink/5 text-ink/50 line-through";
    return "border-ink/10 bg-white text-ink/50";
  }
  if (option === props.chosen) return "border-orange bg-lemon/40 font-semibold";
  return "border-ink/15 bg-white hover:border-orange hover:bg-lemon/30";
}
</script>

<template>
  <div class="space-y-5">
    <p lang="ja" class="text-center text-5xl font-bold sm:text-6xl">{{ item.prompt }}</p>
    <div class="grid gap-2 sm:grid-cols-2">
      <button
        v-for="option in item.options"
        :key="option"
        class="option rounded-2xl border-2 px-4 py-3 text-left text-lg transition disabled:cursor-default"
        :class="optionLook(option)"
        :disabled="locked"
        @click="$emit('choose', option)"
      >
        {{ option }}
      </button>
    </div>
  </div>
</template>
