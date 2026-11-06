import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import KeikoNote from "../src/components/KeikoNote.vue";

const copy = { title: "Catatan Keiko", weekOf: "Minggu", queued: "sedang memeriksa", none: "seminggu sekali" };

describe("KeikoNote", () => {
  it("shows the note with its citations as marks, not brackets", () => {
    const note = { week_start: "2026-11-02", body: "Kamu di unit 4 [ref:curriculum]." };
    const wrapper = mount(KeikoNote, { props: { note, isQueued: false, copy } });
    expect(wrapper.text()).not.toContain("[ref:");
    expect(wrapper.find("sup.cite").text()).toBe("curriculum");
  });

  it("says Keiko is checking while a check is queued and there is no note yet", () => {
    const wrapper = mount(KeikoNote, { props: { note: null, isQueued: true, copy } });
    expect(wrapper.find('[role="status"]').text()).toBe("sedang memeriksa");
    expect(wrapper.text()).not.toContain("seminggu sekali");
  });
});
