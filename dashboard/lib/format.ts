
export function formatTime(time: string): string {
  const [h, m] = time.split(":");
  const hour = Number(h);
  return `${hour % 12 || 12}:${m} ${hour >= 12 ? "PM" : "AM"}`;
}

export function formatDate(iso: string, options: { weekday?: boolean } = {}): string {
  const date = new Date(`${iso}T00:00:00`);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat("en-IN", {
    weekday: options.weekday === false ? undefined : "short",
    day: "numeric",
    month: "short",
    year: sameYear ? undefined : "numeric",
  }).format(date);
}

export function formatDateTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
    .format(new Date(timestamp))
    .replace(/am|pm/, (s) => s.toUpperCase());
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export function initials(name: string): string {
  return name
    .replace(/^dr\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

const GENDER: Record<string, string> = { MALE: "Male", FEMALE: "Female", OTHER: "Other" };

export function describePatient(p: { age: number | null; gender: string | null }): string {
  return [p.age !== null ? `${p.age} yrs` : null, p.gender ? GENDER[p.gender] : null].filter(Boolean).join(", ");
}

export const LANGUAGES: Record<string, string> = { en: "English", hi: "Hindi" };
