import { describe, expect, it } from "vitest";
import { parseEvents } from "../src/lib/sse";

describe("parseEvents", () => {
  it("splits complete events and keeps the unfinished tail", () => {
    const { events, rest } = parseEvents("event: delta\r\ndata: Halo\r\n\r\nevent: done\r\ndata: {\"is_ver");
    expect(events).toEqual([{ event: "delta", data: "Halo" }]);
    expect(rest).toBe('event: done\r\ndata: {"is_ver');
  });

  it("joins several data lines with a newline", () => {
    const { events } = parseEvents("event: delta\ndata: satu\ndata: dua\n\n");
    expect(events).toEqual([{ event: "delta", data: "satu\ndua" }]);
  });

  it("keeps the leading space of a word piece after the colon's one space", () => {
    const { events } = parseEvents("event: delta\ndata:  kata\n\n");
    expect(events[0]?.data).toBe(" kata");
  });
});
