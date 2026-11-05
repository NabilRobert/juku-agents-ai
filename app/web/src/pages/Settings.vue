<script setup lang="ts">
// Pengaturan: level, time zone and exam date; and the learner's own data, to download or delete.
import PostForm from "../components/PostForm.vue";

defineProps<{
  learner: { target_level: number; timezone: string; exam_date: string | null };
  levels: number[];
  timezones: string[];
  deleteError: boolean;
  copy: Record<
    | "title" | "targetLevel" | "timeZone" | "examDate" | "save"
    | "yourData" | "download" | "deleteExplain" | "deleteError" | "delete",
    string
  >;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title mb-4">{{ copy.title }}</h1>
    <PostForm action="/pengaturan" class="card grid gap-4 sm:grid-cols-2">
      <label>
        <span class="label">{{ copy.targetLevel }}</span>
        <select name="target_level" class="field">
          <option v-for="level in levels" :key="level" :value="level" :selected="level === learner.target_level">N{{ level }}</option>
        </select>
      </label>
      <label>
        <span class="label">{{ copy.timeZone }}</span>
        <select name="timezone" class="field">
          <option v-for="zone in timezones" :key="zone" :value="zone" :selected="zone === learner.timezone">{{ zone }}</option>
        </select>
      </label>
      <label>
        <span class="label">{{ copy.examDate }}</span>
        <input type="date" name="exam_date" :value="learner.exam_date ?? ''" class="field" />
      </label>
      <div class="flex items-end"><button type="submit" class="btn">{{ copy.save }}</button></div>
    </PostForm>

    <section class="card mt-6">
      <h2 class="section-title">{{ copy.yourData }}</h2>
      <p class="mt-2"><a href="/unduh-data" class="btn-quiet">↓ {{ copy.download }}</a></p>
      <PostForm action="/hapus-data" class="mt-5 space-y-2 rounded-xl border border-red-200 bg-red-50 p-4">
        <p class="text-sm">{{ copy.deleteExplain }}</p>
        <p v-if="deleteError" role="alert" class="text-sm font-semibold text-red-700">{{ copy.deleteError }}</p>
        <div class="flex flex-wrap gap-2">
          <input name="confirm" autocomplete="off" aria-label="HAPUS" class="field max-w-48" />
          <button type="submit" class="btn-danger">{{ copy.delete }}</button>
        </div>
      </PostForm>
    </section>
  </div>
</template>
