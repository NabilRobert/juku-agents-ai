<script setup lang="ts">
// One kanji that shows its readings, meaning and words using it when hovered, focused or tapped. The
// details come from /kanji/<character> once per page (cached), so a page doesn't carry every kanji's data.
// A tap only opens it (a phone fires mouseenter then click); tapping elsewhere closes it, as mouseleave.
import { ref } from "vue";
import { useStudyCopy } from "../lib/study";
import type { KanjiEntry } from "../lib/types";

const props = defineProps<{ character: string }>();
const copy = useStudyCopy();
const isOpen = ref(false);
const entry = ref<KanjiEntry | null | undefined>(undefined);

/** Close only when focus leaves the kanji and its popup, so a click on one of the popup's words still lands. */
function closeUnlessInside(event: FocusEvent): void {
  const target = event.currentTarget as HTMLElement;
  if (!target.contains(event.relatedTarget as Node | null)) isOpen.value = false;
}

async function open(): Promise<void> {
  isOpen.value = true;
  if (entry.value === undefined) entry.value = await kanjiDetails(props.character);
}
</script>

<script lang="ts">
const details = new Map<string, Promise<KanjiEntry | null>>();

/** One request per kanji per page; null when the character isn't a JLPT kanji. */
function kanjiDetails(character: string): Promise<KanjiEntry | null> {
  if (!details.has(character)) {
    const request = fetch(`/kanji/${encodeURIComponent(character)}`).then((response) =>
      response.ok ? (response.json() as Promise<KanjiEntry>) : null,
    );
    details.set(character, request);
  }
  return details.get(character) as Promise<KanjiEntry | null>;
}
</script>

<template>
  <span
    class="kanji relative cursor-help rounded-sm decoration-orange decoration-dotted underline-offset-4 hover:bg-lemon/60 hover:underline focus:bg-lemon/60 focus:outline-none"
    tabindex="0"
    @mouseenter="open"
    @focus="open"
    @click.stop="open"
    @mouseleave="isOpen = false"
    @focusout="closeUnlessInside"
    @keydown.escape="isOpen = false"
    >{{ character
    }}<span
      v-if="isOpen"
      role="tooltip"
      class="absolute top-full left-1/2 z-30 w-64 max-w-[80vw] -translate-x-1/2 cursor-auto rounded-2xl border border-gold/50 bg-white p-3 text-left text-sm leading-normal font-normal text-ink shadow-xl"
    >
      <span v-if="entry === undefined" class="muted">{{ copy.loading }}</span>
      <span v-else-if="entry === null" class="muted">{{ copy.notKanji }}</span>
      <template v-else>
        <span class="flex items-start gap-3">
          <span lang="ja" class="text-4xl leading-none font-bold">{{ entry.character }}</span>
          <span class="flex-1">
            <span class="block font-semibold">{{ entry.meanings.slice(0, 3).join(", ") }}</span>
            <span class="muted block text-xs">N{{ entry.level }}<template v-if="entry.strokes"> · {{ entry.strokes }} {{ copy.strokes }}</template></span>
          </span>
        </span>
        <span v-if="entry.onyomi.length" class="mt-2 block"><span class="chip mr-1">音</span><span lang="ja">{{ entry.onyomi.join("、") }}</span></span>
        <span v-if="entry.kunyomi.length" class="mt-1 block"><span class="chip mr-1">訓</span><span lang="ja">{{ entry.kunyomi.slice(0, 6).join("、") }}</span></span>
        <span v-if="entry.words.length" class="mt-2 block border-t border-gold/30 pt-2">
          <span class="muted block text-xs">{{ copy.kanjiWords }}</span>
          <a
            v-for="word in entry.words"
            :key="word.word_id"
            :href="`/kata/${word.word_id}`"
            class="flex items-baseline justify-between gap-2 py-0.5 no-underline hover:text-orange"
          >
            <span lang="ja"><span class="font-bold">{{ word.word }}</span> <span class="text-ink/70">{{ word.reading }}</span></span>
            <span class="truncate text-xs text-ink/60">{{ word.is_known ? `✓ ${copy.known}` : word.meaning }}</span>
          </a>
        </span>
      </template>
    </span></span
  >
</template>
