<script setup lang="ts">
// One run in the Run Inspector (AG3): its facts, every draft and review, the decision, and the report.
interface Issue {
  severity?: string;
  kind?: string;
  reason: string;
  quote?: string;
}
interface Attempt {
  agent: string;
  attempt: number;
  is_approved: boolean;
  reason: string;
  content: unknown;
  grade: string | null;
  issues: Issue[] | null;
  code_issues: Issue[] | null;
}

defineProps<{
  run: { id: number; kind: string; status: string; public_id: string; week_start: string; attempts: number; started_at: string; finished_at: string | null };
  facts: string;
  attempts: Attempt[];
  report: { body: string; is_fallback: boolean } | null;
}>();
</script>

<template>
  <p class="mb-2"><a href="/admin/runs" class="text-sm">← Run Inspector</a></p>
  <h1 class="page-title">Run {{ run.id }}: {{ run.kind }}, {{ run.status }}</h1>
  <p class="muted mt-1">
    {{ run.public_id }} · week of {{ run.week_start }} · attempts {{ run.attempts }} · {{ run.started_at }} to
    {{ run.finished_at ?? "-" }}
  </p>
  <h2 class="section-title mt-6 mb-2">Facts</h2>
  <pre class="overflow-x-auto rounded-2xl bg-ink p-4 text-xs text-lemon">{{ facts }}</pre>
  <section
    v-for="(attempt, index) in attempts"
    :key="index"
    class="card mt-4 border-l-4 text-sm"
    :class="attempt.is_approved ? 'border-l-amber' : 'border-l-red-600'"
  >
    <h2 class="section-title">
      {{ attempt.agent }}, attempt {{ attempt.attempt + 1 }}: {{ attempt.is_approved ? "approved" : "blocked" }} ({{ attempt.reason }})
    </h2>
    <pre class="mt-2 overflow-x-auto rounded-xl bg-cream p-3 text-xs">{{ JSON.stringify(attempt.content, null, 1) }}</pre>
    <p class="mt-2 font-semibold">Tadashi: grade {{ attempt.grade ?? "none" }}</p>
    <ul class="list-disc pl-5">
      <li v-for="(issue, at) in attempt.issues ?? []" :key="at">{{ issue.severity }}: {{ issue.reason }} ({{ issue.quote }})</li>
    </ul>
    <p class="mt-2 font-semibold">Code's checks:</p>
    <ul class="list-disc pl-5">
      <li v-for="(issue, at) in attempt.code_issues ?? []" :key="at">{{ issue.kind }}: {{ issue.reason }}</li>
      <li v-if="!attempt.code_issues?.length">none</li>
    </ul>
  </section>
  <h2 class="section-title mt-6 mb-2">Report<template v-if="report?.is_fallback"> (facts-only fallback)</template></h2>
  <p class="card text-sm whitespace-pre-line">{{ report?.body ?? "-" }}</p>
</template>
