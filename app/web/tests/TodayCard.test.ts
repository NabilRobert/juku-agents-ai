import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import TodayCard from "../src/components/TodayCard.vue";
import { CSRF } from "../src/lib/csrf";
import type { TodayPlan } from "../src/lib/types";

const unit = { unit_id: 3, level: 5, number: 3, words_total: 15, words_known: 2, grammar_total: 1, grammar_studied: 0,
  sentences_total: 5, sentences_read: 0, status: "current" as const };
const today: TodayPlan = {
  unit, new_words: [], words_target: 10, words_done: 10, grammar: { grammar_id: "wa", pattern: "は", meaning: "topic", is_studied: false },
  grammar_done: 0, sentences: [], sentences_target: 3, sentences_done: 3, reviews_due: 0, quiz_target: 10, quiz_done: 10,
  week: [{ day: "2026-11-05", done: 23, target: 24, is_future: false }, { day: "2026-11-06", done: 0, target: 24, is_future: true }],
};
const copy = new Proxy({}, { get: (_target, key) => String(key) }) as InstanceType<typeof TodayCard>["$props"]["copy"];
const mountWith = (plan: TodayPlan) => mount(TodayCard, { props: { today: plan, copy, weekdays: ["Thu", "Fri"] }, global: { provide: { [CSRF as symbol]: "t" } } });

describe("TodayCard", () => {
  it("is done once the last part, the grammar point, is understood", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response('{"done": true}')));
    const wrapper = mountWith(today);
    expect(wrapper.text()).not.toContain("allDone");
    await wrapper.find("button.understand").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("allDone");
    expect(wrapper.find("li").attributes("aria-label")).toBe("Thu: 24 / 24");
    vi.unstubAllGlobals();
  });

  it("says the curriculum is finished when there is no current unit", () => {
    const wrapper = mountWith({ ...today, unit: null, grammar: null });
    expect(wrapper.text()).toContain("finished");
    expect(wrapper.find('a[href^="/rencana/unit/"]').exists()).toBe(false);
  });

  it("sends the learner to the quiz when reviews are due", () => {
    const wrapper = mountWith({ ...today, reviews_due: 4 });
    expect(wrapper.find("a.reviews").attributes("href")).toBe("/kuis");
  });
});
