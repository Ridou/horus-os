/**
 * Pure time-formatting helpers. No side effects, no globals, fully testable.
 */

const MINUTE = 60;
const HOUR = MINUTE * 60;
const DAY = HOUR * 24;
const WEEK = DAY * 7;
const MONTH = DAY * 30;
const YEAR = DAY * 365;

/**
 * Format a timestamp as a compact relative string, e.g. "3m ago", "2h ago",
 * "just now". Accepts an ISO string, epoch milliseconds, or a Date.
 *
 * @param now - optional reference time (defaults to Date.now), injectable for tests.
 */
export function timeAgo(
  input: string | number | Date | null | undefined,
  now: number = Date.now(),
): string {
  if (input === null || input === undefined) return "never";

  const then =
    input instanceof Date
      ? input.getTime()
      : typeof input === "number"
        ? input
        : Date.parse(input);

  if (Number.isNaN(then)) return "unknown";

  const seconds = Math.round((now - then) / 1000);

  // Treat future and near-now timestamps as "just now". This also guards
  // against minor clock skew between the client and the local backend.
  if (seconds < 30) return "just now";
  if (seconds < MINUTE) return `${seconds}s ago`;
  if (seconds < HOUR) return `${Math.floor(seconds / MINUTE)}m ago`;
  if (seconds < DAY) return `${Math.floor(seconds / HOUR)}h ago`;
  if (seconds < WEEK) return `${Math.floor(seconds / DAY)}d ago`;
  if (seconds < MONTH) return `${Math.floor(seconds / WEEK)}w ago`;
  if (seconds < YEAR) return `${Math.floor(seconds / MONTH)}mo ago`;
  return `${Math.floor(seconds / YEAR)}y ago`;
}

/** Format a timestamp as an absolute, locale-independent UTC string. */
export function formatTimestamp(
  input: string | number | Date | null | undefined,
): string {
  if (input === null || input === undefined) return "";
  const date =
    input instanceof Date ? input : new Date(input);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ` +
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`
  );
}

/** Human-readable byte size, e.g. "1.4 KB", "3.2 MB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}
