import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ActivityCalendar from "../src/components/ActivityCalendar.vue";
import { addDays, mondayOf, shadeOf } from "../src/lib/calendar";

const copy = {
  title: "Aktivitasmu",
  activeDays: "hari aktif",
  activeDay: "hari aktif (satu)",
  less: "Sedikit",
  more: "Banyak",
  actions: "aktivitas",
  quizAnswers: "jawaban kuis",
  wordsMarked: "kata ditandai",
  sentencesRead: "kalimat dibaca",
  questions: "pertanyaan ke Shiori",
  weekdays: ["Sen", "Rab", "Jum"],
};
const busy = { day: "2026-11-05", count: 8, quiz_answers: 5, words_marked: 2, sentences_read: 0, questions: 1 };
const quiet = { day: "2026-11-03", count: 2, quiz_answers: 2, words_marked: 0, sentences_read: 0, questions: 0 };

describe("calendar arithmetic", () => {
  it("starts weeks on Monday", () => {
    expect(mondayOf("2026-11-05")).toBe("2026-11-02"); // a Thursday
    expect(mondayOf("2026-11-02")).toBe("2026-11-02");
  });

  it("crosses months and years by whole days", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });

  it("shades a day against the learner's own busiest day, empty for none", () => {
    expect([0, 1, 2, 4, 8].map((count) => shadeOf(count, 8))).toEqual([0, 1, 1, 2, 4]);
  });
});

describe("ActivityCalendar", () => {
  const wrapper = mount(ActivityCalendar, { props: { days: [quiet, busy], today: "2026-11-05", weeks: 26, copy } });

  it("draws every day of the half year up to today, and none after", () => {
    const days = wrapper.findAll("rect.day");
    expect(days).toHaveLength(25 * 7 + 4); // 25 full weeks, then Monday to Thursday
    expect(days.at(-1)!.find("title").text()).toContain("2026-11-05");
  });

  it("makes the busiest day the darkest, and says what was done", () => {
    const busiest = wrapper.findAll("rect.day").find((rect) => rect.find("title").text().startsWith("2026-11-05"))!;
    expect(busiest.attributes("data-shade")).toBe("4");
    expect(busiest.find("title").text()).toBe("2026-11-05: 8 aktivitas (5 jawaban kuis, 2 kata ditandai, 1 pertanyaan ke Shiori)");
    expect(wrapper.text()).toContain("2 hari aktif");
  });
});
