/**
 * What one indicator cell is entitled to show — for every indicator, not just σ.
 *
 * A snapshot describes the last *settled* daily bar, because price-sync drops
 * the forming one (`drop_unsettled_last_bar`). So while a venue is open, every
 * stored value in that snapshot is the previous session's, rendered beside a
 * live price from this one. Most indicators have no choice about that; a few
 * hold a settled baseline the live quote completes, and those declare a
 * `live` block on their descriptor.
 *
 * Both halves of that go through {@link resolveIndicatorValue}: it dispatches
 * to the live resolver when one is declared, and otherwise reports the stored
 * number together with how far behind the session it belongs to. Call sites
 * that name a field by hand agree only by luck — the row, the sort key and the
 * tooltip disagreeing is precisely how a stale reading gets rendered as a
 * current one.
 */

import type { IndicatorSummary, Quote } from "@/lib/types"
import {
  getDescriptorByField,
  getNumericValue,
  type LiveResolverId,
} from "@/lib/indicator-registry"
import {
  resolveSigma,
  sessionsBehind,
  sigmaWithheldTitle,
  type SigmaResolution,
  type ValueSource,
  type WithheldReason,
} from "@/lib/sigma"

/** A resolver turns quote + snapshot into one live-or-settled number. */
type LiveResolver = (
  quote: Quote | undefined,
  snapshot: IndicatorSummary | undefined,
) => SigmaResolution

const LIVE_RESOLVERS: Record<LiveResolverId, LiveResolver> = {
  sigma: resolveSigma,
}

/** Why a resolver blanked its cell, in that resolver's own terms. Only a live
 * resolver has anything to say: a settled field is either present or absent,
 * and "absent" has no explanation beyond itself. */
const WITHHELD_TITLES: Record<LiveResolverId, (reason: WithheldReason) => string | null> = {
  sigma: sigmaWithheldTitle,
}

export type IndicatorValueResolution =
  | {
      status: "ok"
      value: number
      source: ValueSource
      /** Sessions between the bar this value describes and the quote's live
       * session: 0 for a live score or a settled bar that *is* today, 1 for
       * the usual mid-session case, Infinity for off-the-end, null when no
       * quote dates it. */
      behind: number | null
    }
  | { status: "withheld"; reason: WithheldReason; behind: number | null }

/**
 * Resolve one field for one asset.
 *
 * `behind` is reported on the settled path too, and that is the point: the
 * number is right, its session is not today's, and only the distance says
 * which. A caller that renders the value without it is the bug this module
 * exists for.
 */
export function resolveIndicatorValue(
  field: string,
  quote: Quote | undefined,
  snapshot: IndicatorSummary | undefined,
): IndicatorValueResolution {
  const behind = snapshot ? sessionsBehind(snapshot, quote) : null
  const descriptor = getDescriptorByField(field)
  const live = descriptor?.live

  if (live && live.field === field) {
    const resolved = LIVE_RESOLVERS[live.resolver](quote, snapshot)
    return resolved.status === "ok"
      ? { status: "ok", value: resolved.sigma, source: resolved.source, behind }
      : { status: "withheld", reason: resolved.reason, behind }
  }

  const stored = getNumericValue(snapshot?.values, field)
  if (stored == null) {
    return { status: "withheld", reason: { kind: "no_data" }, behind }
  }
  return { status: "ok", value: stored, source: "settled", behind }
}

/** Human explanation for a blanked cell, or null when there is nothing useful
 * to say (the cell is then a mute dash rather than a lying tooltip). */
export function indicatorWithheldTitle(
  field: string,
  reason: WithheldReason,
): string | null {
  const live = getDescriptorByField(field)?.live
  if (!live || live.field !== field) return null
  return WITHHELD_TITLES[live.resolver](reason)
}

/** Sort key: the resolved number, or null so unresolvable rows sort last.
 * Identical to what the row renders, by construction. */
export function indicatorSortKey(resolution: IndicatorValueResolution): number | null {
  return resolution.status === "ok" ? resolution.value : null
}

/**
 * True when a shown value describes a session the quote has already left.
 *
 * Not "behind >= 1": during any open session *every* settled indicator is one
 * bar back, so flagging that flags the whole table and says nothing. Two or
 * more is a stored-history hole — actionable, and the thing worth catching the
 * eye.
 */
export function isAbnormallyBehind(resolution: IndicatorValueResolution): boolean {
  if (resolution.status === "ok" && resolution.source === "live") return false
  const { behind } = resolution
  return behind != null && behind >= 2
}

/** The session a settled value describes, phrased for a tooltip, or null when
 * it is already the live one (or undatable). */
export function settledSessionTitle(
  label: string,
  resolution: IndicatorValueResolution,
  snapshot: IndicatorSummary | undefined,
): string | null {
  if (resolution.status !== "ok" || resolution.source === "live") return null
  const { behind } = resolution
  if (behind == null || behind < 1) return null
  const asOf = snapshot?.as_of
  const session = asOf ? `the ${asOf} session` : "an earlier session"
  if (!Number.isFinite(behind)) {
    return `${label} is ${session} — stored prices are behind the live quote.`
  }
  if (behind === 1) {
    return `${label} is ${session}, the last completed one. Daily indicators only score settled bars, so today's is not in it yet.`
  }
  return `${label} is ${session}, ${behind} trading sessions behind the live quote. A background job backfills missing sessions automatically; see the Stats page.`
}
