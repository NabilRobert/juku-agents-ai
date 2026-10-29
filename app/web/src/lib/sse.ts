// Server-sent events from a fetch response: the chat is a POST, which EventSource can't send.
export interface ServerEvent {
  event: string;
  data: string;
}

const EVENT_END = /\r?\n\r?\n/;
const LINE_END = /\r?\n/;

function parseBlock(block: string): ServerEvent {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(LINE_END)) {
    const colon = line.indexOf(":");
    if (colon < 0) continue;
    const field = line.slice(0, colon);
    // The spec drops exactly one space after the colon; a word piece's own leading space survives.
    const value = line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }
  return { event, data: data.join("\n") };
}

/** Split a stream of text into events: `event:` and `data:` lines, ended by a blank line. */
export function parseEvents(buffer: string): { events: ServerEvent[]; rest: string } {
  const events: ServerEvent[] = [];
  let rest = buffer;
  for (let found = EVENT_END.exec(rest); found; found = EVENT_END.exec(rest)) {
    events.push(parseBlock(rest.slice(0, found.index)));
    rest = rest.slice(found.index + found[0].length);
  }
  return { events, rest };
}

export async function* readEvents(response: Response): AsyncGenerator<ServerEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseEvents(buffer);
    buffer = rest;
    yield* events;
  }
}
