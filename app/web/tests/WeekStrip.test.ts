import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WeekStrip from "../src/components/WeekStrip.vue";

const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const week = [24, 13, 0, 1, 0, 0, 0].map((done, offset) => ({
  day: `2026-11-0${offset + 2}`, done, target: 24, is_future: offset > 3,
}));

describe("WeekStrip", () => {
  it("ticks only the days whose lesson was all done", () => {
    const days = mount(WeekStrip, { props: { week, title: "This week", weekdays } }).findAll("li");
    expect(days.map((day) => day.text().includes("✓"))).toEqual([true, false, false, false, false, false, false]);
    expect(days[1]!.attributes("aria-label")).toBe("Tue: 13 / 24");
  });

  it("dims the days still to come", () => {
    const days = mount(WeekStrip, { props: { week, title: "This week", weekdays } }).findAll("li");
    expect(days.map((day) => day.classes().includes("opacity-40"))).toEqual([false, false, false, false, true, true, true]);
  });
});
