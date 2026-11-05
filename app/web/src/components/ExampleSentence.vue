<script setup lang="ts">
// An example sentence: its Japanese with furigana, its translation, and its explanation behind a button.
import { ref } from "vue";
import { useStudyCopy } from "../lib/study";
import type { Example, SentenceBreakdown as Breakdown } from "../lib/types";
import JapaneseText from "./JapaneseText.vue";
import SentenceBreakdown from "./SentenceBreakdown.vue";

defineProps<{ example: Example; breakdown?: Breakdown }>();
const copy = useStudyCopy();
const isExplained = ref(false);
</script>

<template>
  <div>
    <div class="flex items-start justify-between gap-3">
      <p class="text-xl leading-loose font-medium sm:text-2xl"><JapaneseText :text="example.ja" :furigana="example.furigana" /></p>
      <button v-if="breakdown" type="button" class="explain btn-quiet shrink-0 py-1 text-xs" :aria-expanded="isExplained" @click="isExplained = !isExplained">
        {{ isExplained ? copy.hide : `💡 ${copy.explain}` }}
      </button>
    </div>
    <p v-if="example.en" class="muted">{{ example.en }}</p>
    <SentenceBreakdown v-if="breakdown && isExplained" :breakdown="breakdown" />
    <slot />
  </div>
</template>
