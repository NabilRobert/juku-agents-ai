<script setup lang="ts">
// A sentence explained from the data: each word with its reading and meaning (yellow if the learner knows
// it), the particles and endings, and the grammar points it may use, each linked to its explanation.
import { useStudyCopy } from "../lib/study";
import type { BreakdownToken, SentenceBreakdown } from "../lib/types";
import JapaneseText from "./JapaneseText.vue";

defineProps<{ breakdown: SentenceBreakdown }>();
const copy = useStudyCopy();

function tokenLook(token: BreakdownToken): string {
  if (token.kind === "word" && token.words.length) {
    return token.words.every((word) => word.is_known) ? "border-gold bg-lemon/50" : "border-ink/15 bg-white";
  }
  return token.kind === "grammar" ? "border-transparent bg-ink/5 text-ink/80" : "border-transparent";
}
</script>

<template>
  <div class="mt-3 space-y-3 rounded-xl bg-cream p-3">
    <div>
      <p class="muted mb-1 text-xs font-semibold">{{ copy.words }}</p>
      <ol class="flex flex-wrap items-end gap-1.5">
        <template v-for="(token, index) in breakdown.tokens" :key="index">
          <li v-if="token.kind !== 'symbol'" class="token flex min-w-10 flex-col items-center rounded-lg border px-2 py-1" :class="tokenLook(token)">
            <span class="text-[0.65rem] text-ink/60" lang="ja">{{ token.reading !== token.surface ? token.reading : " " }}</span>
            <JapaneseText :text="token.surface" class="text-lg font-semibold" />
            <a
              v-for="word in token.words"
              :key="word.word_id"
              :href="`/kata/${word.word_id}`"
              class="max-w-28 truncate text-[0.7rem] text-ink/70"
              >{{ word.meanings[0] ?? word.word }}</a
            >
          </li>
        </template>
      </ol>
    </div>
    <div v-if="breakdown.grammar.length">
      <p class="muted text-xs font-semibold">{{ copy.grammar }}</p>
      <p class="muted mb-1 text-[0.7rem]">{{ copy.grammarNote }}</p>
      <ul class="flex flex-wrap gap-1.5">
        <li v-for="point in breakdown.grammar" :key="point.grammar_id">
          <a
            :href="`/tata-bahasa/${point.grammar_id}`"
            class="grammar-point inline-flex items-center gap-1.5 rounded-full border border-ink/15 bg-white px-2.5 py-1 text-xs no-underline hover:border-orange"
            :title="point.meaning"
          >
            <span class="chip px-1.5 py-0 text-[0.6rem]">N{{ point.level }}</span>
            <span lang="ja" class="font-semibold">{{ point.pattern }}</span>
          </a>
        </li>
      </ul>
    </div>
  </div>
</template>
