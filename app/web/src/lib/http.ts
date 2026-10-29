// The islands' one way to write: JSON, with the page's CSRF token in a header (app/src/juku_app/web.py).
export function postJson(url: string, body: unknown, csrf: string): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(body),
  });
}

/** The CSRF token from the page's <meta name="csrf-token">. */
export function pageCsrf(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
}

/** JSON the server rendered into a <script type="application/json" id="..."> tag. */
export function pageJson<T>(id: string): T {
  return JSON.parse(document.getElementById(id)?.textContent ?? "null") as T;
}
