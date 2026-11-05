<script setup lang="ts">
// Masuk: the invite code, the only way in (ADR-029).
import PostForm from "../components/PostForm.vue";

defineProps<{ hasError: boolean; copy: Record<"welcome" | "explain" | "error" | "code" | "signIn", string> }>();
</script>

<template>
  <section class="card mx-auto mt-6 max-w-md text-center sm:p-8">
    <span lang="ja" class="mx-auto grid size-16 place-items-center rounded-2xl bg-linear-to-br from-lemon to-orange text-4xl font-black shadow-md">塾</span>
    <h1 class="page-title mt-4">{{ copy.welcome }}</h1>
    <p class="muted mt-1">{{ copy.explain }}</p>
    <p v-if="hasError" role="alert" class="alert mt-4 text-left">{{ copy.error }}</p>
    <PostForm action="/masuk" class="mt-5 space-y-3 text-left">
      <label>
        <span class="label">{{ copy.code }}</span>
        <input name="code" autocomplete="off" required class="field font-mono" />
      </label>
      <button type="submit" class="btn w-full">{{ copy.signIn }}</button>
    </PostForm>
  </section>
</template>
