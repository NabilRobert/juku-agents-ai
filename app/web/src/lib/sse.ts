// Server-sent events from a fetch response: the chat is a POST, which EventSource can't send.
export interface ServerEvent {
  event: string;
  data: string;
}

/** Split a stream of text into events: `event:` and `data:` lines, ended by a blank line. */
export function parseEvents(buffer: string): { events: ServerEvent[]; rest: string } {
  throw new Error(`not built yet: ${buffer.length}`);
}

export async function* readEvents(response: Response): AsyncGenerator<ServerEvent> {
  throw new Error(`not built yet: ${response.status}`);
}
