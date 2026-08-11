// Assembles everything the dense board renders: the tile roster with per-tile
// σ/%/phase resolution, the section grouping, and the coverage numbers.
//
// σ resolution reuses the group table's exact cascade (computeLiveVnr →
// stored vnr unless isStoredVnrStale → explain the blank) so the board can
// never disagree with the table about the same asset.

import { useMemo } from "react"
import { useQueries } from "@tanstack/react-query"
import { api, type Asset, type SparklinePoint } from "@/lib/api"
import {
  keys,
  STALE_5MIN,
  useDataHealth,
  useGroups,
  useIndicators,
  useMarketPhases,
  useTheses,
} from "@/lib/queries"
import { useQuotes } from "@/lib/quote-stream"
import {
  computeLiveVnr,
  getNumericValue,
  isStoredVnrStale,
} from "@/lib/indicator-registry"
import { marketState } from "@/lib/market-state"
import { VNR_BASELINE_SESSIONS, type PctWindow, PCT_WINDOWS } from "./color-scale"

export type Phase = "premarket" | "open" | "aftermarket" | "closed"

/** Why a tile has no σ reading — each state gets its own honest copy. */
export type NoReadingReason =
  | { kind: "feed_behind" }
  | { kind: "gap"; sessions: number; nextScanSeconds: number | null }
  | { kind: "warmup"; bars: number; needed: number }
  | { kind: "unknown" }

export interface Tile {
  symbol: string
  name: string
  currency: string
  /** σ-Move via the live-first cascade; null → see reason. */
  sigma: number | null
  reason: NoReadingReason | null
  /** Today's % change (live quote first, stored bar fallback). */
  todayPct: number | null
  /** % change over each board window (from the shared 1mo series). */
  windowPct: Record<PctWindow, number | null>
  phase: Phase | null
  /** Venue calendar name + next scheduled phase change (tooltip). */
  calendar: string | null
  nextBell: string | null
  /** Whether the phase came from a live quote (vs the schedule fallback). */
  liveState: boolean
}

export interface BoardSection {
  key: string
  title: string
  /** Thesis colour edge (thesis grouping only). */
  accent: string | null
  tiles: Tile[]
}

export type GroupBy = "group" | "thesis"

/** Per-symbol % change series over the covering month, shared by the tiles'
 * %-mode, the Movers card, and the tooltips — one fetch, three windows. */
function useWindowReturns(symbols: string[]) {
  const { data: groups } = useGroups()
  const sparkQueries = useQueries({
    queries: (groups ?? []).map((g) => ({
      queryKey: keys.groupSparklines(g.id, "1mo"),
      queryFn: () => api.groups.sparklines(g.id, "1mo"),
      staleTime: STALE_5MIN,
    })),
  })
  // useQueries returns new result arrays each render; depend on a stable
  // fingerprint of the data so the merge doesn't recompute per render.
  const loaded = sparkQueries.filter((q) => q.data).length
  const series = useMemo(() => {
    const merged: Record<string, SparklinePoint[]> = {}
    for (const q of sparkQueries) {
      if (!q.data) continue
      for (const [sym, points] of Object.entries(q.data)) {
        if (!merged[sym] || points.length > merged[sym].length) merged[sym] = points
      }
    }
    return merged
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see fingerprint note above
  }, [loaded, groups])

  const quotes = useQuotes()
  return useMemo(() => {
    const out: Record<string, Record<PctWindow, number | null>> = {}
    const today = new Date()
    for (const sym of symbols) {
      const points = series[sym]
      const per = {} as Record<PctWindow, number | null>
      for (const w of PCT_WINDOWS) {
        per[w.value] = null
        if (!points?.length) continue
        const cutoff = new Date(today)
        cutoff.setDate(cutoff.getDate() - w.days)
        const cutoffIso = cutoff.toISOString().slice(0, 10)
        // Baseline = last close at or before the window start; a series that
        // doesn't reach back that far has no honest answer for this window.
        let base: SparklinePoint | null = null
        for (const p of points) {
          if (p.date <= cutoffIso) base = p
          else break
        }
        if (!base || base.close === 0) continue
        const last = quotes[sym]?.price ?? points[points.length - 1].close
        per[w.value] = ((last - base.close) / base.close) * 100
      }
      out[sym] = per
    }
    return out
  }, [symbols, series, quotes])
}

const EMPTY_WINDOWS: Record<PctWindow, number | null> = { "1wk": null, "2wk": null, "1mo": null }

export function useBoardData(groupBy: GroupBy) {
  const { data: groups, isLoading: groupsLoading } = useGroups()
  const { data: theses } = useTheses()
  const quotes = useQuotes()
  const { data: phases } = useMarketPhases()
  const { data: health } = useDataHealth()

  // The roster: every asset in any group — "the whole book". Assets known
  // only through a thesis still get tiles in thesis grouping.
  const roster = useMemo(() => {
    const bySymbol = new Map<string, Asset>()
    for (const g of groups ?? []) for (const a of g.assets) bySymbol.set(a.symbol, a)
    if (groupBy === "thesis")
      for (const t of theses ?? []) for (const a of t.assets) bySymbol.set(a.symbol, a)
    return bySymbol
  }, [groups, theses, groupBy])

  const symbols = useMemo(() => [...roster.keys()].sort(), [roster])
  const { data: snapshots } = useIndicators(symbols)
  const windowReturns = useWindowReturns(symbols)

  const symbolPhase = useMemo(() => {
    const out: Record<string, { calendar: string; phase: Phase; nextBell: string | null }> = {}
    for (const [cal, entry] of Object.entries(phases ?? {}))
      for (const sym of entry.symbols)
        out[sym] = { calendar: cal, phase: entry.phase, nextBell: entry.next_change_at }
    return out
  }, [phases])

  const tiles = useMemo(() => {
    const out = new Map<string, Tile>()
    for (const [symbol, asset] of roster) {
      const quote = quotes[symbol]
      const snap = snapshots?.[symbol]
      const values = snap?.values

      let sigma = computeLiveVnr(quote, values, snap?.close)
      let reason: NoReadingReason | null = null
      if (sigma == null) {
        const stale = isStoredVnrStale(quote, snap?.close)
        const stored = getNumericValue(values, "vnr")
        if (stored != null && !stale) {
          sigma = stored
        } else if (stale) {
          reason = { kind: "feed_behind" }
        } else {
          const gap = getNumericValue(values, "vnr_gap_sessions")
          const bars = snap?.bars ?? null
          if (gap != null) {
            reason = { kind: "gap", sessions: gap, nextScanSeconds: health?.next_scan_in_seconds ?? null }
          } else if (bars != null && bars < VNR_BASELINE_SESSIONS) {
            reason = { kind: "warmup", bars, needed: VNR_BASELINE_SESSIONS }
          } else {
            reason = { kind: "unknown" }
          }
        }
      }

      const scheduled = symbolPhase[symbol]
      const liveState = quote?.market_state != null
      const phase: Phase | null = liveState
        ? marketState(quote.market_state).phase
        : scheduled?.phase ?? null

      out.set(symbol, {
        symbol,
        name: asset.name,
        currency: asset.currency,
        sigma,
        reason,
        todayPct: quote?.change_percent ?? snap?.change_pct ?? null,
        windowPct: windowReturns[symbol] ?? EMPTY_WINDOWS,
        phase,
        calendar: scheduled?.calendar ?? null,
        nextBell: scheduled?.nextBell ?? null,
        liveState,
      })
    }
    return out
  }, [roster, quotes, snapshots, windowReturns, symbolPhase, health])

  const sections = useMemo<BoardSection[]>(() => {
    const toTiles = (list: Asset[]) =>
      list.map((a) => tiles.get(a.symbol)).filter((t): t is Tile => !!t)
    if (groupBy === "group") {
      return (groups ?? [])
        .map((g) => ({ key: `g${g.id}`, title: g.name, accent: null, tiles: toTiles(g.assets) }))
        .filter((s) => s.tiles.length > 0)
    }
    const out: BoardSection[] = (theses ?? [])
      .map((t) => ({ key: `t${t.id}`, title: t.name, accent: t.color, tiles: toTiles(t.assets) }))
      .filter((s) => s.tiles.length > 0)
    const inThesis = new Set((theses ?? []).flatMap((t) => t.assets.map((a) => a.symbol)))
    const rest = [...tiles.values()].filter((t) => !inThesis.has(t.symbol))
    if (rest.length) out.push({ key: "no-thesis", title: "No thesis", accent: null, tiles: rest })
    return out
  }, [groupBy, groups, theses, tiles])

  const coverage = useMemo(() => {
    const all = [...tiles.values()]
    return {
      total: all.length,
      scored: all.filter((t) => t.sigma != null).length,
      open: all.filter((t) => t.phase === "open").length,
    }
  }, [tiles])

  return { sections, tiles, coverage, isLoading: groupsLoading }
}
