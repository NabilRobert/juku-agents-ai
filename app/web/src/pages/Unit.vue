<script setup lang="ts">
// One curriculum unit: its words, kanji, grammar points and sentences. Each is marked done in place (no
// reload), and the unit's bars follow; the unit is done when all three are full.
import { computed } from "vue";
import ExampleSentence from "../components/ExampleSentence.vue";
import KanjiChar from "../components/KanjiChar.vue";
import ProgressBar from "../components/ProgressBar.vue";
import WordCard from "../components/WordCard.vue";
import { useAction } from "../lib/action";
import type { SentenceBreakdown, UnitDetail } from "../lib/types";

type UnitCopy =
  | "unit" | "back" | "words" | "kanji" | "grammar" | "sentences" | "iKnowThis" | "youKnowThis" | "examples"
  | "understand" | "understood" | "read" | "markRead" | "previous" | "next" | "unitDone" | "wordsKnown"
  | "grammarStudied" | "sentencesRead" | "failed" | "noSentences";

const props = defineProps<{ detail: UnitDetail; breakdowns: Record<string, SentenceBreakdown>; copy: Record<UnitCopy, string> }>();
const { run, pending, done, failed } = useAction();

const isKnown = (wordId: string) => done.has(`word:${wordId}`) || props.detail.words.some((w) => w.word_id === wordId && w.is_known);
const isStudied = (grammarId: string) =>
  done.has(`grammar:${grammarId}`) || props.detail.grammar.some((g) => g.grammar_id === grammarId && g.is_studied);
const isRead = (sentenceId: number) =>
  done.has(`sentence:${sentenceId}`) || props.detail.sentences.some((s) => s.sentence_id === sentenceId && s.is_read);

const wordsKnown = computed(() => props.detail.words.filter((word) => isKnown(word.word_id)).length);
const grammarStudied = computed(() => props.detail.grammar.filter((point) => isStudied(point.grammar_id)).length);
const sentencesRead = computed(() => props.detail.sentences.filter((sentence) => isRead(sentence.sentence_id)).length);
const isUnitDone = computed(
  () =>
    props.detail.unit.status === "done" ||
    (wordsKnown.value === props.detail.words.length &&
      grammarStudied.value === props.detail.grammar.length &&
      sentencesRead.value === props.detail.sentences.length),
);
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-6">
    <p><a href="/rencana" class="text-sm">← {{ copy.back }}</a></p>
    <section class="card space-y-3">
      <div class="flex items-center justify-between gap-3">
        <h1 class="page-title"><span class="chip mr-2 align-middle">N{{ detail.unit.level }}</span>{{ copy.unit }} {{ detail.unit.number }}</h1>
        <span v-if="isUnitDone" class="chip bg-lemon text-ink" role="status">✓ {{ copy.unitDone }}</span>
      </div>
      <ProgressBar :value="wordsKnown" :total="detail.words.length" :label="copy.wordsKnown" />
      <ProgressBar :value="grammarStudied" :total="detail.grammar.length" :label="copy.grammarStudied" tone="gold" />
      <ProgressBar v-if="detail.sentences.length" :value="sentencesRead" :total="detail.sentences.length" :label="copy.sentencesRead" />
    </section>
    <p v-if="failed" class="alert" role="alert">{{ copy.failed }}</p>

    <section>
      <h2 class="section-title mb-3">{{ copy.words }}</h2>
      <ul class="grid gap-3 sm:grid-cols-2">
        <li v-for="word in detail.words" :key="word.word_id" class="flex">
          <WordCard :word="word" :examples-label="copy.examples" class="w-full">
            <template #action>
              <p v-if="isKnown(word.word_id)" class="chip bg-lemon text-ink">✓ {{ copy.youKnowThis }}</p>
              <button v-else type="button" class="known btn-quiet w-full" :disabled="pending.has(`word:${word.word_id}`)"
                @click="run(`word:${word.word_id}`, `/rencana/kata/${encodeURIComponent(word.word_id)}/dikuasai`)">
                ✓ {{ copy.iKnowThis }}
              </button>
            </template>
          </WordCard>
        </li>
      </ul>
    </section>

    <section v-if="detail.kanji.length">
      <h2 class="section-title mb-3">{{ copy.kanji }}</h2>
      <p class="flex flex-wrap gap-2 text-3xl font-bold">
        <span v-for="kanji in detail.kanji" :key="kanji" class="card px-3 py-2"><KanjiChar :character="kanji" /></span>
      </p>
    </section>

    <section v-if="detail.grammar.length">
      <h2 class="section-title mb-3">{{ copy.grammar }}</h2>
      <ul class="space-y-2">
        <li v-for="point in detail.grammar" :key="point.grammar_id" class="card flex flex-wrap items-center justify-between gap-3 p-4">
          <a :href="`/tata-bahasa/${point.grammar_id}`" class="no-underline">
            <span lang="ja" class="block text-lg font-bold">{{ point.pattern }}</span>
            <span class="muted block">{{ point.meaning }}</span>
          </a>
          <p v-if="isStudied(point.grammar_id)" class="chip bg-lemon text-ink">✓ {{ copy.understood }}</p>
          <button v-else type="button" class="understand btn-quiet" :disabled="pending.has(`grammar:${point.grammar_id}`)"
            @click="run(`grammar:${point.grammar_id}`, `/rencana/tata-bahasa/${encodeURIComponent(point.grammar_id)}/paham`)">
            {{ copy.understand }}
          </button>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="section-title mb-3">{{ copy.sentences }}</h2>
      <p v-if="!detail.sentences.length" class="muted">{{ copy.noSentences }}</p>
      <ul class="space-y-3">
        <li v-for="sentence in detail.sentences" :key="sentence.sentence_id" class="card border-l-4 border-l-amber">
          <ExampleSentence :example="sentence" :breakdown="breakdowns[sentence.ja]">
            <div class="mt-3 flex justify-end">
              <p v-if="isRead(sentence.sentence_id)" class="chip bg-lemon text-ink">✓ {{ copy.read }}</p>
              <button v-else type="button" class="mark-read btn-quiet" :disabled="pending.has(`sentence:${sentence.sentence_id}`)"
                @click="run(`sentence:${sentence.sentence_id}`, `/rencana/kalimat/${sentence.sentence_id}/dibaca`)">
                {{ copy.markRead }}
              </button>
            </div>
          </ExampleSentence>
        </li>
      </ul>
    </section>

    <nav class="flex justify-between gap-3">
      <a v-if="detail.previous_unit_id" :href="`/rencana/unit/${detail.previous_unit_id}`" class="btn-quiet">← {{ copy.previous }}</a>
      <span v-else></span>
      <a v-if="detail.next_unit_id" :href="`/rencana/unit/${detail.next_unit_id}`" class="btn">{{ copy.next }} →</a>
    </nav>
  </div>
</template>
