import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import Unit from "../src/pages/Unit.vue";
import { CSRF } from "../src/lib/csrf";
import { STUDY } from "../src/lib/study";
import type { UnitDetail } from "../src/lib/types";

const status = { unit_id: 3, level: 5, number: 3, words_total: 2, words_known: 1, grammar_total: 1, grammar_studied: 0,
  sentences_total: 1, sentences_read: 1, status: "current" as const };
const detail: UnitDetail = {
  unit: status,
  words: [
    { word_id: "w1", word: "一", reading: "いち", meanings: ["one"], is_known: true },
    { word_id: "w2", word: "人", reading: "ひと", meanings: ["person"], is_known: false },
  ],
  kanji: ["一", "人"],
  grammar: [{ grammar_id: "wa", pattern: "は", meaning: "topic", is_studied: false }],
  sentences: [{ sentence_id: 9, ja: "一人", furigana: null, en: "alone", is_read: true }],
  previous_unit_id: 2,
  next_unit_id: 4,
};
const copy = new Proxy({}, { get: (_target, key) => String(key) }) as InstanceType<typeof Unit>["$props"]["copy"];

function mounted() {
  return mount(Unit, {
    props: { detail, breakdowns: {}, copy },
    global: { provide: { [CSRF as symbol]: "t", [STUDY as symbol]: {} } },
  });
}

describe("Unit", () => {
  it("marks a word known in place and fills the unit when the grammar point follows", async () => {
    const fetchMock = vi.fn(async (_url: string) => new Response('{"done": true}'));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mounted();
    expect(wrapper.text()).not.toContain("unitDone");
    await wrapper.find("button.known").trigger("click");
    await wrapper.find("button.understand").trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual(["/rencana/kata/w2/dikuasai", "/rencana/tata-bahasa/wa/paham"]);
    expect(wrapper.findAll("button.known")).toHaveLength(0);
    expect(wrapper.text()).toContain("unitDone");
    vi.unstubAllGlobals();
  });

  it("keeps the button and says so when marking fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
    const wrapper = mounted();
    await wrapper.find("button.known").trigger("click");
    await flushPromises();
    expect(wrapper.find("button.known").exists()).toBe(true);
    expect(wrapper.find('[role="alert"]').text()).toBe("failed");
    vi.unstubAllGlobals();
  });
});
