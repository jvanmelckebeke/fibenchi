/**
 * Asset-detail analysis window.
 *
 * A window always ends at the latest available data and is fully described by a
 * start. It is either one of the backend's fixed periods, or an explicit start
 * date ("since"). Custom windows are served frontend-only: we fetch the smallest
 * fixed period that *covers* the start, then slice the result to the exact day —
 * no backend arbitrary-range endpoint required.
 */

import { formatDateLong } from "./format"

/** Calendar-day span of each fixed backend period. Mirrors backend `PERIOD_DAYS`. */
export const PERIOD_DAYS: Record<string, number> = {
  "1mo": 30,
  "3mo": 90,
  "6mo": 180,
  "1y": 365,
  "2y": 730,
  "5y": 1825,
}

/** Fixed periods understood by the backend, smallest → largest. */
export const STANDARD_PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

const LARGEST_PERIOD = STANDARD_PERIODS[STANDARD_PERIODS.length - 1]

export type AssetWindow =
  | { kind: "period"; period: string }
  | { kind: "since"; start: string } // ISO yyyy-mm-dd

export interface ResolvedWindow {
  /** Backend period to actually fetch (guaranteed to cover the window). */
  fetchPeriod: string
  /** ISO date to slice the fetched series at, or null to use the whole period. */
  startDate: string | null
  /** Human label for the active window. */
  label: string
}

/** Format a Date as a local-time ISO date (avoids the UTC shift of toISOString). */
function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

/** Today as a local ISO date. */
export function todayISO(): string {
  return toISODate(new Date())
}

/** ISO date `days` calendar days before today (local). */
export function relativeStart(days: number): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - days)
  return toISODate(d)
}

/** ISO date for Jan 1 of the current year. */
export function ytdStart(): string {
  return `${new Date().getFullYear()}-01-01`
}

/** Smallest fixed period whose span covers `days`; clamps to the largest. */
export function coveringPeriod(days: number): string {
  for (const p of STANDARD_PERIODS) {
    if (PERIOD_DAYS[p] >= days) return p
  }
  return LARGEST_PERIOD
}

function daysSince(isoStart: string): number {
  const start = new Date(isoStart + "T00:00:00")
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return Math.ceil((now.getTime() - start.getTime()) / 86_400_000)
}

function formatSinceLabel(isoStart: string): string {
  return `since ${formatDateLong(isoStart)}`
}

export function resolveWindow(window: AssetWindow): ResolvedWindow {
  if (window.kind === "period") {
    return { fetchPeriod: window.period, startDate: null, label: window.period }
  }
  return {
    fetchPeriod: coveringPeriod(daysSince(window.start)),
    startDate: window.start,
    label: formatSinceLabel(window.start),
  }
}
