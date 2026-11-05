<script setup lang="ts">
// Japanese text with its furigana as <ruby>, every kanji in it hoverable for its readings (KanjiChar).
import { computed } from "vue";
import { furiganaRuns, isKanji } from "../lib/furigana";
import KanjiChar from "./KanjiChar.vue";

const props = defineProps<{ text: string; furigana?: string | null }>();
const runs = computed(() => furiganaRuns(props.text, props.furigana ?? null));
</script>

<template>
  <span lang="ja"
    ><template v-for="(run, index) in runs" :key="index"
      ><ruby v-if="run.reading"
        ><template v-for="(character, at) in [...run.text]" :key="at"
          ><KanjiChar v-if="isKanji(character)" :character="character" /><template v-else>{{ character }}</template></template
        ><rt>{{ run.reading }}</rt></ruby
      ><template v-else
        ><template v-for="(character, at) in [...run.text]" :key="at"
          ><KanjiChar v-if="isKanji(character)" :character="character" /><template v-else>{{ character }}</template></template
        ></template
      ></template
    ></span
  >
</template>
