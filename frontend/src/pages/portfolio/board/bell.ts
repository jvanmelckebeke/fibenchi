// How the board talks about venue phases and the next bell.
//
// Pure vocabulary + formatting, kept out of the tooltip component so the
// wording is testable and lives in one place.

import type { Phase } from "./use-board-data"

export const PHASE_LABEL: Record<Phase, string> = {
  premarket: "pre-market",
  open: "open",
  aftermarket: "after-hours",
  closed: "closed",
}

/** `next_change_at` is the next boundary of whatever phase we're *in*, so what
 * it means depends on the phase we're leaving. "next bell" for closed is not
 * vagueness: that boundary may be the pre-market edge rather than the opening
 * bell, and the calendar doesn't tell us which. */
export const BELL_VERB: Record<Phase, string> = {
  premarket: "opens",
  open: "closes",
  aftermarket: "ends",
  closed: "next bell",
}

/** "2h12" / "14m" — coarse on purpose; the exact time sits next to it. Null
 * once the bell has passed: a stale schedule must not print a negative. */
export function countdown(target: Date, now: Date): string | null {
  const mins = Math.round((target.getTime() - now.getTime()) / 60000)
  if (mins <= 0) return null
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h${String(mins % 60).padStart(2, "0")}`
}
