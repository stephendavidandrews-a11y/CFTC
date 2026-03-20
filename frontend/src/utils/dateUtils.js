/**
 * Date utilities for the CFTC Command Center.
 *
 * Core problem: date-only strings like "2026-03-19" are parsed by
 * `new Date()` as UTC midnight, which in US time zones rolls back to
 * the previous day's evening.  Every date formatter and comparator
 * must normalise date-only strings to noon local time first.
 */

/**
 * Safely parse a date string.  If the value is a date-only string
 * (YYYY-MM-DD, 10 chars), appends "T12:00:00" so the browser treats
 * it as local noon instead of UTC midnight.
 */
export function safeDate(d) {
  if (!d) return null;
  const v = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(v);
}

/** Short date: "Mar 19, 2026" */
export function formatDate(d) {
  const dt = safeDate(d);
  if (!dt || isNaN(dt)) return "\u2014";
  return dt.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Compact date (no year): "Mar 19" */
export function formatDateShort(d) {
  const dt = safeDate(d);
  if (!dt || isNaN(dt)) return "\u2014";
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Full date+time: "Wed, Mar 19, 2026, 2:00 PM" */
export function formatDateTime(d) {
  const dt = safeDate(d);
  if (!dt || isNaN(dt)) return "\u2014";
  return dt.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Relative "time ago" label: "3d ago", "2h ago" */
export function timeAgo(d) {
  const dt = safeDate(d);
  if (!dt || isNaN(dt)) return "\u2014";
  const diff = Date.now() - dt.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/** True if the date is in the past (before today midnight). */
export function isPast(d) {
  const dt = safeDate(d);
  if (!dt) return false;
  return dt < new Date(new Date().toDateString());
}

/** True if the date is within `withinDays` from now (inclusive). */
export function isWithinDays(d, withinDays) {
  const dt = safeDate(d);
  if (!dt) return false;
  const diff = (dt - new Date()) / (1000 * 60 * 60 * 24);
  return diff >= 0 && diff <= withinDays;
}

/** Compute duration string between two date/time strings. */
export function getDuration(start, end) {
  if (!start || !end) return null;
  const s = safeDate(start);
  const e = safeDate(end);
  if (!s || !e) return null;
  const mins = Math.round((e - s) / 60000);
  if (mins <= 0) return null;
  if (mins >= 60) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  return `${mins}m`;
}
