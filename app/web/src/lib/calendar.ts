// The activity calendar's arithmetic: whole days in UTC, so no timezone shifts a square (the server already
// counted each day in the learner's own timezone and sends plain YYYY-MM-DD dates).
const DAY_MS = 24 * 60 * 60 * 1000;
export const SHADES = 4;

export function addDays(isoDate: string, days: number): string {
  return new Date(Date.parse(`${isoDate}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

/** The Monday on or before the date (Monday-first weeks, as in Indonesia). */
export function mondayOf(isoDate: string): string {
  const weekday = (new Date(`${isoDate}T00:00:00Z`).getUTCDay() + 6) % 7;
  return addDays(isoDate, -weekday);
}

/** 0 for no activity; otherwise 1 to SHADES, relative to the learner's own busiest day. */
export function shadeOf(count: number, busiest: number): number {
  if (count <= 0 || busiest <= 0) return 0;
  return Math.min(SHADES, Math.ceil((SHADES * count) / busiest));
}
