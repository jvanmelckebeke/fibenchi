import { memo } from "react"
import { Link } from "react-router-dom"
import { Moon, Sun, Sunrise, Sunset } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { changeColor, formatChangePct } from "@/lib/format"
import { rampColor, pctWindowDef, type ColorMode, type PctWindow } from "./color-scale"
import type { Tile as TileData } from "./use-board-data"

// One shared pulse: every live dot's animation phase is aligned to the wall
// clock (negative delay = time since the epoch mod the cycle), so the board
// reads as one system being alive rather than twinkling noise.
const PING_CYCLE_MS = 2400
function pingDelay(): string {
  return `-${Date.now() % PING_CYCLE_MS}ms`
}

// Day-cycle icons for the venue phase — sun up = market open. Hues stay
// outside the value ramp (yellow/amber/slate, never red or green) so a state
// glyph can never be misread as a value.
export function PhaseIcon({ phase, live }: { phase: TileData["phase"]; live?: boolean }) {
  if (phase == null) return null
  if (phase === "open") {
    return (
      <span className="relative shrink-0" title={live ? "Open (live)" : "Open (scheduled)"}>
        <span
          className="board-ping absolute inset-0.5 rounded-full bg-yellow-300"
          style={{ animationDelay: pingDelay() }}
        />
        <Sun className="phase-icon relative h-4 w-4 text-yellow-300" />
      </span>
    )
  }
  if (phase === "premarket") {
    return <Sunrise className="phase-icon h-4 w-4 shrink-0 text-amber-400" aria-label="Pre-market" />
  }
  if (phase === "aftermarket") {
    return <Sunset className="phase-icon h-4 w-4 shrink-0 text-orange-400" aria-label="After-hours" />
  }
  return <Moon className="phase-icon h-4 w-4 shrink-0 text-current opacity-80" aria-label="Closed" />
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
  const stop = noReading ? null : rampColor(value, mode, window, unit)

  // Every tile prints its own value as text — nothing on the board is
  // encoded by colour alone. A no-reading tile still shows the raw % move,
  // in its up/down colour: the reading is missing, the day is not.
  const valueEl = noReading ? (
    <>
      {mode === "sigma" ? "—σ" : "—%"}
      {mode === "sigma" && tile.todayPct != null && (
        <span className={`ml-1 ${changeColor(tile.todayPct)}`}>
          {formatChangePct(tile.todayPct).text}
        </span>
      )}
    </>
  ) : mode === "sigma" ? (
    fmtSigma(value)
  ) : (
    formatChangePct(value).text
  )

  const windows = (["1wk", "2wk", "1mo"] as const).map((w) => {
    const p = tile.windowPct[w]
    return `${pctWindowDef(w).label}: ${p != null ? formatChangePct(p).text : "—"}`
  })

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          to={`/asset/${tile.symbol}`}
          className={`board-tile flex h-[80px] flex-col justify-between rounded-[3px] px-3 py-2.5 outline-none transition-[filter] hover:brightness-125 focus-visible:ring-2 focus-visible:ring-ring ${noReading ? "board-tile-unread" : ""}`}
          style={stop ? { backgroundColor: stop.color, color: stop.ink } : undefined}
        >
          <span className="flex items-center justify-between gap-1">
            <span className="truncate font-mono text-[14px] font-semibold leading-none">{tile.symbol}</span>
            <PhaseIcon phase={tile.phase} live={tile.liveState} />
          </span>
          <span className="text-[13px] leading-none tabular-nums opacity-90">{valueEl}</span>
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
