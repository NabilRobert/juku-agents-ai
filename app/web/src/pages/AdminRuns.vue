<script setup lang="ts">
// The Run Inspector (AG3): the latest weekly runs, and the feedback job's drafts (never applied). Owner only.
import AdminNav from "../components/AdminNav.vue";

interface RunRow {
  id: number;
  public_id: string;
  week_start: string;
  kind: string;
  status: string;
  attempts: number;
  started_at: string;
  finished_at: string | null;
}
interface DraftRow {
  week_start: string;
  agent: string;
  status: string;
  patterns: unknown;
  draft: string;
}

defineProps<{ runs: RunRow[]; drafts: DraftRow[] }>();
</script>

<template>
  <AdminNav title="Run Inspector" current="runs" />
  <div class="mt-4 overflow-x-auto">
    <table class="data-table">
      <tr><th>Run</th><th>Learner</th><th>Week</th><th>Kind</th><th>Status</th><th>Attempts</th><th>Started</th><th>Finished</th></tr>
      <tr v-for="run in runs" :key="run.id">
        <td><a :href="`/admin/runs/${run.id}`" class="font-semibold">{{ run.id }}</a></td>
        <td class="font-mono">{{ run.public_id }}</td>
        <td>{{ run.week_start }}</td>
        <td>{{ run.kind }}</td>
        <td>
          <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="run.status === 'published' ? 'bg-lemon' : 'bg-ink/10'">{{ run.status }}</span>
        </td>
        <td>{{ run.attempts }}</td>
        <td>{{ run.started_at }}</td>
        <td>{{ run.finished_at ?? "-" }}</td>
      </tr>
      <tr v-if="runs.length === 0"><td colspan="8">No runs yet.</td></tr>
    </table>
  </div>
  <h2 class="section-title mt-8 mb-2">Prompt feedback drafts (never applied)</h2>
  <article v-for="(draft, index) in drafts" :key="index" class="card mt-2 text-sm">
    <p class="font-semibold">{{ draft.week_start }} · {{ draft.agent }} · {{ draft.status }}</p>
    <p class="muted text-xs">{{ draft.patterns }}</p>
    <p class="mt-2 whitespace-pre-line">{{ draft.draft }}</p>
  </article>
  <p v-if="drafts.length === 0" class="muted">No drafts yet.</p>
</template>
