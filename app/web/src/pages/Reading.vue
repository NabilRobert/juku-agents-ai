<script setup lang="ts">
// Bacaan: sentences with one new word each. The ruby HTML comes escaped from the server (ruby.py).
import PostForm from "../components/PostForm.vue";

interface Sentence {
  sentence_id: number;
  ja: string;
  en: string | null;
  new_word: string;
  tatoeba_id: number | null;
}

defineProps<{
  sentences: { sentence: Sentence; ruby: string }[];
  copy: Record<"title" | "intro" | "newWord" | "read" | "empty", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title">{{ copy.title }}</h1>
    <p class="muted mt-1 mb-5">{{ copy.intro }}</p>
    <ul class="space-y-3">
      <li v-for="{ sentence, ruby } in sentences" :key="sentence.sentence_id" class="card border-l-4 border-l-amber">
        <!-- eslint-disable-next-line vue/no-v-html -->
        <p v-if="ruby" lang="ja" class="text-2xl leading-loose font-medium" v-html="ruby"></p>
        <p v-else lang="ja" class="text-2xl leading-loose font-medium">{{ sentence.ja }}</p>
        <p v-if="sentence.en" class="muted mt-1">{{ sentence.en }}</p>
        <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm">
            {{ copy.newWord }}:
            <span lang="ja" class="rounded-md bg-lemon/60 px-1.5 py-0.5 font-bold">{{ sentence.new_word }}</span>
            <template v-if="sentence.tatoeba_id">
              <span class="text-ink/50"> · </span>
              <a :href="`https://tatoeba.org/sentences/show/${sentence.tatoeba_id}`" rel="noopener" class="text-xs"
                >Tatoeba #{{ sentence.tatoeba_id }}</a
              >
            </template>
          </p>
          <PostForm :action="`/bacaan/${sentence.sentence_id}/dibaca`">
            <button type="submit" class="btn-quiet">✓ {{ copy.read }}</button>
          </PostForm>
        </div>
      </li>
      <li v-if="sentences.length === 0" class="alert">{{ copy.empty }}</li>
    </ul>
  </div>
</template>
