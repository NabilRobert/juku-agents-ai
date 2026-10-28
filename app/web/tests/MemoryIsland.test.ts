import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import MemoryIsland from "../src/islands/MemoryIsland.vue";

const copy = {
  notesHeading: "Catatan",
  noNotes: "Belum ada catatan.",
  wordsHeading: "Kata yang kamu kuasai",
  noWords: "Belum ada kata.",
  notedOn: "dicatat",
  daysAgo: "hari lalu",
  right: "benar",
  wrong: "salah",
  remove: "Hapus",
  markWrong: "Ini salah",
  unmark: "Belum dikuasai",
  removed: "Catatan dihapus.",
  markedWrong: "Terima kasih, catatan ditandai salah.",
  unmarked: "Kata ditandai belum dikuasai.",
  failed: "Gagal. Coba lagi.",
  categories: { recurring_confusion: "Sering tertukar" },
  events: { quiz_reading: "kuis bacaan" },
};
const note = {
  note_id: "note-7",
  category: "recurring_confusion",
  text: "Sering salah membaca 読む.",
  evidence: [
    { event_id: 1, event_type: "quiz_reading", word: "読む", reading: "よむ", is_correct: false, occurred_on: "2026-11-02" },
  ],
  noted_on: "2026-11-06",
  age_days: 2,
};
const words = [{ word_id: "w1", word: "食べる", reading: "たべる" }];

function island() {
  return mount(MemoryIsland, { props: { notes: [note], words, copy, csrf: "t" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("MemoryIsland", () => {
  // EDD: it.fails until the island lands in the next commit.
  it.fails("shows each note with its evidence and age", () => {
    const text = island().text();
    expect(text).toContain("Sering salah membaca 読む.");
    expect(text).toContain("Sering tertukar");
    expect(text).toContain("2026-11-02 · kuis bacaan · 読む (よむ) · salah");
    expect(text).toContain("2 hari lalu");
  });

  it.fails("removes a note with the CSRF token and drops it from the page", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = island();
    await wrapper.find("button.remove").trigger("click");
    await flushPromises();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/ingat/catatan/note-7/hapus");
    expect((init as RequestInit).headers).toMatchObject({ "X-CSRF-Token": "t" });
    expect(wrapper.findAll("article.note")).toHaveLength(0);
    expect(wrapper.text()).toContain("Catatan dihapus.");
  });

  it.fails("marks a note wrong", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = island();
    await wrapper.find("button.mark-wrong").trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls[0]![0]).toBe("/ingat/catatan/note-7/salah");
    expect(wrapper.findAll("article.note")).toHaveLength(0);
  });

  it.fails("unmarks a known word", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = island();
    await wrapper.find("button.unmark").trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls[0]![0]).toBe("/ingat/kata/w1/belum");
    expect(wrapper.findAll("li.known-word")).toHaveLength(0);
  });

  it.fails("keeps the note and says so when the server refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    const wrapper = island();
    await wrapper.find("button.remove").trigger("click");
    await flushPromises();
    expect(wrapper.findAll("article.note")).toHaveLength(1);
    expect(wrapper.text()).toContain("Gagal. Coba lagi.");
  });

  it.fails("says when there is nothing remembered yet", () => {
    const text = mount(MemoryIsland, { props: { notes: [], words: [], copy, csrf: "t" } }).text();
    expect(text).toContain("Belum ada catatan.");
    expect(text).toContain("Belum ada kata.");
  });
});
