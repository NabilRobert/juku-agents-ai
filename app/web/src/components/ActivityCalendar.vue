<script setup lang="ts">
// GitHub-style activity calendar (Arthur, 2026-11-05): one square per day for half a year, darker for busier
// days, in Juku's palette. Plain SVG: a library would be heavier than a grid of squares.
import { computed } from "vue";
import { SHADES, addDays, mondayOf, shadeOf } from "../lib/calendar";

interface ActiveDay {
  day: string;
  count: number;
  quiz_answers: number;
  words_marked: number;
  sentences_read: number;
  questions: number;
}
type CalendarCopy = Record<
  "title" | "activeDays" | "less" | "more" | "actions" | "quizAnswers" | "wordsMarked" | "sentencesRead" | "questions",
  string
> & { weekdays: string[] };

const props = defineProps<{ days: ActiveDay[]; today: string; weeks: number; copy: CalendarCopy }>();

// Empty, then lemon, gold, orange and ink: the darkest square is the busiest day.
const FILLS = ["#fffbea", "#ffeb3b", "#fbc02d", "#ff8f00", "#212121"];
const CELL = 11;
const STEP = 14;
const LEFT = 26;
const TOP = 16;

const byDay = computed(() => new Map(props.days.map((day) => [day.day, day])));
const busiest = computed(() => Math.max(0, ...props.days.map((day) => day.count)));
const first = computed(() => addDays(mondayOf(props.today), -7 * (props.weeks - 1)));
const monthName = new Intl.DateTimeFormat(document.documentElement.lang || "id", { month: "short", timeZone: "UTC" });

const cells = computed(() => {
  const shown = [];
  for (let week = 0; week < props.weeks; week += 1) {
    for (let weekday = 0; weekday < 7; weekday += 1) {
      const day = addDays(first.value, 7 * week + weekday);
      if (day > props.today) break;
      const activity = byDay.value.get(day);
      shown.push({ day, week, weekday, shade: shadeOf(activity?.count ?? 0, busiest.value), activity });
    }
  }
  return shown;
});

/** A month's short name above the first week that starts in it. */
const months = computed(() => {
  const labels = [];
  for (let week = 0; week < props.weeks; week += 1) {
    const monday = addDays(first.value, 7 * week);
    if (week === 0 || monday.slice(5, 7) !== addDays(monday, -7).slice(5, 7)) {
      labels.push({ week, name: monthName.format(new Date(`${monday}T00:00:00Z`)) });
    }
  }
  return labels;
});

function describe(day: string, activity: ActiveDay | undefined): string {
  if (!activity) return `${day}: 0 ${props.copy.actions}`;
  const parts = [
    [activity.quiz_answers, props.copy.quizAnswers],
    [activity.words_marked, props.copy.wordsMarked],
    [activity.sentences_read, props.copy.sentencesRead],
    [activity.questions, props.copy.questions],
  ].filter(([count]) => Number(count) > 0);
  return `${day}: ${activity.count} ${props.copy.actions} (${parts.map(([count, what]) => `${count} ${what}`).join(", ")})`;
}
</script>

<template>
  <section class="card">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="section-title">{{ copy.title }}</h2>
      <p class="muted"><strong class="text-ink">{{ days.length }}</strong> {{ copy.activeDays }}</p>
    </div>
    <svg
      class="mt-3 w-full"
      :viewBox="`0 0 ${LEFT + weeks * STEP} ${TOP + 7 * STEP}`"
      role="img"
      :aria-label="`${copy.title}: ${days.length} ${copy.activeDays}`"
    >
      <text v-for="month in months" :key="month.week" :x="LEFT + month.week * STEP" y="10" class="fill-ink/60 text-[9px]">
        {{ month.name }}
      </text>
      <text v-for="(name, index) in copy.weekdays" :key="name" x="0" :y="TOP + (2 * index) * STEP + 9" class="fill-ink/60 text-[9px]">
        {{ name }}
      </text>
      <rect
        v-for="cell in cells"
        :key="cell.day"
        class="day"
        :data-shade="cell.shade"
        :x="LEFT + cell.week * STEP"
        :y="TOP + cell.weekday * STEP"
        :width="CELL"
        :height="CELL"
        rx="2"
        :fill="FILLS[cell.shade]"
        :stroke="cell.shade === 0 ? '#21212120' : 'none'"
      >
        <title>{{ describe(cell.day, cell.activity) }}</title>
      </rect>
    </svg>
    <p class="muted mt-2 flex items-center justify-end gap-1 text-xs">
      {{ copy.less }}
      <svg v-for="shade in SHADES + 1" :key="shade" width="11" height="11" aria-hidden="true">
        <rect width="11" height="11" rx="2" :fill="FILLS[shade - 1]" :stroke="shade === 1 ? '#21212120' : 'none'" />
      </svg>
      {{ copy.more }}
    </p>
  </section>
</template>
