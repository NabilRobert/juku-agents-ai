<script setup lang="ts">
// The owner page (ADR-029): invite codes, every learner, and the owner actions log. English, owner only.
import AdminNav from "../components/AdminNav.vue";
import PostForm from "../components/PostForm.vue";

interface LearnerRow {
  public_id: string;
  nickname: string;
  role: string;
  target_level: number;
  created_at: string;
  last_active_at: string | null;
}
interface ActionRow {
  acted_at: string;
  owner: string | null;
  place: string;
  action: string;
  subject: string | null;
  detail: unknown;
}

defineProps<{
  learners: LearnerRow[];
  actions: ActionRow[];
  maxCodes: number;
  newCodes: string[];
  error: string;
  removed: string;
  removedRows: number;
}>();
</script>

<template>
  <AdminNav title="Learners" current="learners" />
  <p v-if="error" class="alert mt-4" role="alert">{{ error }}</p>
  <p v-if="removed" class="alert mt-4" role="status">Removed {{ removed }} ({{ removedRows }} rows).</p>
  <section v-if="newCodes.length" class="mt-4 rounded-2xl bg-linear-to-br from-lemon to-amber p-5 shadow-sm" aria-labelledby="new-codes">
    <h2 id="new-codes" class="section-title">New invite codes</h2>
    <p class="text-sm">Shown once: only their hashes are kept. Give each to one person.</p>
    <ul class="mt-2 space-y-1 font-mono text-sm">
      <li v-for="code in newCodes" :key="code" class="rounded-lg bg-white/80 px-3 py-1.5 select-all">{{ code }}</li>
    </ul>
  </section>

  <PostForm action="/admin/learners/codes" class="card mt-4 flex flex-wrap items-end gap-3">
    <label><span class="label">Codes</span> <input type="number" name="count" value="1" min="1" :max="maxCodes" class="field w-24" /></label>
    <button class="btn">Issue invite codes</button>
  </PostForm>

  <div class="mt-4 overflow-x-auto">
    <table class="data-table">
      <tr><th>Public ID</th><th>Nickname</th><th>Role</th><th>Level</th><th>Joined</th><th>Last active</th><th>Remove</th></tr>
      <tr v-for="learner in learners" :key="learner.public_id">
        <td class="font-mono">{{ learner.public_id }}</td>
        <td>{{ learner.nickname }}</td>
        <td><span v-if="learner.role === 'owner'" class="chip">owner</span><template v-else>{{ learner.role }}</template></td>
        <td>N{{ learner.target_level }}</td>
        <td>{{ learner.created_at.slice(0, 10) }}</td>
        <td>{{ learner.last_active_at?.slice(0, 10) ?? "-" }}</td>
        <td>
          <template v-if="learner.role === 'owner'">-</template>
          <PostForm v-else action="/admin/learners/remove" class="flex gap-2">
            <input type="hidden" name="public_id" :value="learner.public_id" />
            <input name="confirm" placeholder="type the public ID" :aria-label="`Type ${learner.public_id} to confirm`" class="field w-40 py-1 text-xs" />
            <button class="btn-danger py-1">Remove</button>
          </PostForm>
        </td>
      </tr>
    </table>
  </div>

  <h2 class="section-title mt-8 mb-2">Owner actions</h2>
  <div class="overflow-x-auto">
    <table class="data-table">
      <tr><th>When</th><th>By</th><th>From</th><th>Action</th><th>Learner</th><th>Detail</th></tr>
      <tr v-for="(action, index) in actions" :key="index">
        <td>{{ action.acted_at }}</td>
        <td>{{ action.owner ?? "-" }}</td>
        <td>{{ action.place }}</td>
        <td>{{ action.action }}</td>
        <td>{{ action.subject ?? "-" }}</td>
        <td class="text-xs">{{ action.detail }}</td>
      </tr>
      <tr v-if="actions.length === 0"><td colspan="6">None yet.</td></tr>
    </table>
  </div>
</template>
