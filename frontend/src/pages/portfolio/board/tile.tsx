import { memo } from "react"
import { Link } from "react-router-dom"
import { ArrowRightFromLine, ArrowRightToLine, Moon, Sun } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { changeColor, formatChangePct } from "@/lib/format"
import { rampColor, type ColorMode } from "./color-scale"
import { TileTooltip } from "./tile-tooltip"
import type { Tile as TileData } from "./use-board-data"

// One shared pulse: every live dot's animation phase is aligned to the wall
// clock (negative delay = time since the epoch mod the cycle), so the board
// reads as one system being alive rather than twinkling noise.
const PING_CYCLE_MS = 2400
function pingDelay(): string {
  return `-${Date.now() % PING_CYCLE_MS}ms`
}

// Venue-phase icons: sun up = open, moon = closed, and the extended sessions
// read as arrows against the open/close boundary — into the line before it
// opens, out of the line after it closes. All glyphs render in the tile's own
// ink (currentColor): the shape carries the state, so no hue competes with the
// value ramp.
export function PhaseIcon({ phase, live }: { phase: TileData["phase"]; live?: boolean }) {
  if (phase == null) return null
  if (phase === "open") {
    // No native `title` here: this span sits inside the Radix TooltipTrigger,
    // so the browser's own tooltip would surface on top of the styled card ~500
    // ms later. The live/scheduled distinction lives in the card's source line.
    return (
      <span className="relative shrink-0" aria-label={live ? "Open (live)" : "Open (scheduled)"}>
        <span
          className="board-ping absolute inset-0.5 rounded-full bg-current"
          style={{ animationDelay: pingDelay() }}
        />
        <Sun className="phase-icon relative h-3.5 w-3.5 text-current 2xl:h-4 2xl:w-4" />
      </span>
    )
  }
  if (phase === "premarket") {
    return <ArrowRightToLine className="phase-icon h-3.5 w-3.5 shrink-0 text-current opacity-80 2xl:h-4 2xl:w-4" aria-label="Pre-market" />
  }
  if (phase === "aftermarket") {
    return <ArrowRightFromLine className="phase-icon h-3.5 w-3.5 shrink-0 text-current opacity-80 2xl:h-4 2xl:w-4" aria-label="After-hours" />
  }
  return <Moon className="phase-icon h-3.5 w-3.5 shrink-0 text-current opacity-80 2xl:h-4 2xl:w-4" aria-label="Closed" />
}

function fmtSigma(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}σ`
}

export const BoardTile = memo(function BoardTile({
  tile,
  mode,
  span,
}: {
  tile: TileData
  mode: ColorMode
  /** Day-adaptive ramp span (±σ or ±% — see sigmaUnit / pctSpan). */
  span: number
}) {
  // % mode is *today's* move — the multi-day windows live in the Movers card.
  const value = mode === "sigma" ? tile.sigma : tile.todayPct
  const noReading = value == null
  const stop = noReading ? null : rampColor(value, span)

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

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          to={`/asset/${tile.symbol}`}
          className={`board-tile flex h-[62px] flex-col justify-between rounded-[3px] px-2 py-1.5 2xl:h-[80px] 2xl:px-3 2xl:py-2.5 outline-none transition-[filter] hover:brightness-125 focus-visible:ring-2 focus-visible:ring-ring ${noReading ? "board-tile-unread" : ""}`}
          style={stop ? { backgroundColor: stop.color, color: stop.ink } : undefined}
        >
          <span className="flex items-center justify-between gap-1">
            <span className="truncate font-mono text-[12px] font-semibold 2xl:text-[14px] leading-none">{tile.symbol}</span>
            <PhaseIcon phase={tile.phase} live={tile.liveState} />
          </span>
          <span className="text-[11px] leading-none tabular-nums 2xl:text-[13px] opacity-90">{valueEl}</span>
        </Link>
      </TooltipTrigger>
      {/* The default TooltipContent surface is bg-foreground/text-background —
          near-white on this board. The app's finance colours are unusable on
          it: emerald-400 measures 1.86:1 there against 7.44:1 on bg-popover,
          red-400 2.67:1 against 5.17:1. Hence the explicit popover surface;
          p-0 because the card owns its own padding and dividers.

          `[&>svg]` is the Radix arrow specifically — it's filled foreground by
          the shared primitive and would otherwise stay white. The card is a
          div, so its own icons and sparkline aren't direct children. */}
      <TooltipContent
        side="top"
        className="w-fit max-w-none rounded-lg border border-border bg-popover p-0 text-foreground shadow-lg [&>svg]:fill-popover"
      >
        <TileTooltip tile={tile} mode={mode} span={span} />
      </TooltipContent>
    </Tooltip>
  )
})
