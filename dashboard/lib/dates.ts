// Calendar dates as "YYYY-MM-DD" strings, computed in the hospital's timezone.
// (new Date().toISOString() is UTC, so "today" would be yesterday for the first
// 5.5 hours of every day in India.)

/** Today's date in `timeZone` (an IANA name such as "Asia/Kolkata"); browser zone if omitted. */
export function todayIn(timeZone?: string): string {
  try {
    // The en-CA locale formats dates as YYYY-MM-DD.
    return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
  } catch {
    return new Intl.DateTimeFormat("en-CA").format(new Date());
  }
}

/** `iso` shifted by `days` (calendar arithmetic, immune to DST and the browser's zone). */
export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const shifted = new Date(Date.UTC(y, m - 1, d + days));
  return shifted.toISOString().slice(0, 10);
}

/** ISO weekday of `iso`: 1 = Monday ... 7 = Sunday (matches the backend's available_days). */
export function isoWeekday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const jsDay = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 = Sunday
  return jsDay === 0 ? 7 : jsDay;
}
