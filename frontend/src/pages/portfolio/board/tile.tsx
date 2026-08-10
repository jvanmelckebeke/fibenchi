import { memo } from "react"
import { Link } from "react-router-dom"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { formatChangePct } from "@/lib/format"
import { rampStop, pctWindowDef, type ColorMode, type PctWindow } from "./color-scale"
import type { Tile as TileData } from "./use-board-data"

// One shared pulse: every live dot's animation phase is aligned to the wall
// clock (negative delay = time since the epoch mod the cycle), so the board
// reads as one system being alive rather than twinkling noise.
const PING_CYCLE_MS = 2400
function pingDelay(): string {
  return `-${Date.now() % PING_CYCLE_MS}ms`
}

function PhaseDot({ phase, live }: { phase: TileData["phase"]; live: boolean }) {
  if (phase == null) return null
  // Hues deliberately outside the value ramp (cyan/amber) so a state dot can
  // never be misread as a value; ringed near-white to survive any tile colour.
  if (phase === "open") {
    return (
      <span className="board-dot relative shrink-0" title={live ? "Open (live)" : "Open (scheduled)"}>
        <span className="board-dot-ping absolute inset-0 rounded-full bg-cyan-400" style={{ animationDelay: pingDelay() }} />
        <span className="relative block h-full w-full rounded-full bg-cyan-400 ring-[1.5px] ring-white/80" />
      </span>
    )
  }
  if (phase === "premarket" || phase === "aftermarket") {
    return (
      <span className="board-dot shrink-0" title={phase === "premarket" ? "Pre-market" : "After-hours"}>
        <span className="block h-full w-full rounded-full bg-amber-400 ring-[1.5px] ring-white/80" />
      </span>
    )
  }
  return (
    <span className="board-dot shrink-0" title="Closed">
      <span className="block h-full w-full rounded-full bg-zinc-800 ring-[1.5px] ring-white/60" />
    </span>
  )
}

function reasonCopy(t: TileData): string | null {
  switch (t.reason?.kind) {
    case "feed_behind":
      return "price feed behind the live quote · heal retry within ~10 min"
    case "gap": {
      const scan = t.reason.nextScanSeconds
      const when = scan != null ? `next scan ~${Math.max(1, Math.round(scan / 60))} min` : "runs automatically"
      return `spans a ${t.reason.sessions}-session gap · hole heal, ${when}`
    }
    case "warmup":
      return `building baseline · ${t.reason.bars}/${t.reason.needed} bars`
    case "unknown":
      return "no σ reading"
    default:
      return null
  }
}

function fmtSigma(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}σ`
}

export const BoardTile = memo(function BoardTile({
  tile,
  mode,
  window,
  unit,
}: {
  tile: TileData
  mode: ColorMode
  window: PctWindow
  /** Day-adaptive σ ramp unit (see sigmaUnit). */
  unit: number
}) {
  const pct = tile.windowPct[window]
  const value = mode === "sigma" ? tile.sigma : pct
  const noReading = value == null
  const stop = noReading ? null : rampStop(value, mode, window, unit)

  // Every tile prints its own value as text — nothing on the board is
  // encoded by colour alone. A no-reading tile still shows the raw % move.
  const valueText = noReading
    ? mode === "sigma"
      ? `—σ ${tile.todayPct != null ? formatChangePct(tile.todayPct).text : ""}`.trim()
      : "—%"
    : mode === "sigma"
      ? fmtSigma(value)
      : formatChangePct(value).text

  const windows = (["1wk", "2wk", "1mo"] as const).map((w) => {
    const p = tile.windowPct[w]
    return `${pctWindowDef(w).label}: ${p != null ? formatChangePct(p).text : "—"}`
  })

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          to={`/asset/${tile.symbol}`}
          className={`board-tile flex h-[66px] flex-col justify-between rounded-[3px] px-2.5 py-2 outline-none transition-[filter] hover:brightness-125 focus-visible:ring-2 focus-visible:ring-ring ${noReading ? "board-tile-unread" : ""}`}
          style={stop ? { backgroundColor: stop.color, color: stop.ink } : undefined}
        >
          <span className="flex items-center justify-between gap-1">
            <span className="truncate font-mono text-[13px] font-semibold leading-none">{tile.symbol}</span>
            <PhaseDot phase={tile.phase} live={tile.liveState} />
          </span>
          <span className="text-[12px] leading-none tabular-nums opacity-90">{valueText}</span>
        </Link>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[260px]">
        <div className="space-y-1 text-xs">
          <div className="font-semibold">
            {tile.symbol} <span className="font-normal text-muted-foreground">{tile.name}</span>
          </div>
          <div>
            σ-Move today:{" "}
            {tile.sigma != null ? fmtSigma(tile.sigma) : (reasonCopy(tile) ?? "no reading")}
          </div>
          {tile.todayPct != null && <div>today: {formatChangePct(tile.todayPct).text}</div>}
          <div className="text-muted-foreground">{windows.join(" · ")}</div>
          {tile.calendar && (
            <div className="text-muted-foreground">
              {tile.calendar} · {tile.phase ?? "?"}
              {tile.nextBell && ` · next bell ${new Date(tile.nextBell).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
            </div>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  )
})
