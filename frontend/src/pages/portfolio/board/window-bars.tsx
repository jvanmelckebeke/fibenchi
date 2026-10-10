import { PCT_WINDOWS } from "./color-scale"
import { windowBarFill } from "./move-percentile"
import type { Tile } from "./use-board-data"

// One track per window on a dark rail, filled from the left to the move's
// percentile in the symbol's own history of moves over that window, so a run of
// the mill week is a short stub and the biggest month in two years runs the
// full width. Without enough history the track stays empty. Pastel fill plus a
// soft glow keeps the sign readable over the tile's own green or red ramp.
// Numbers live in the tooltip.
export function WindowBars({
  windowPct,
  windowPercentile,
}: {
  windowPct: Tile["windowPct"]
  windowPercentile: Tile["windowPercentile"]
}) {
  return (
    <span aria-hidden className="flex gap-[3px]">
      {PCT_WINDOWS.map((w) => {
        const v = windowPct[w.value]
        const fill = windowBarFill(windowPercentile[w.value])
        return (
          <span key={w.value} className="h-[3px] flex-1 overflow-hidden rounded-full bg-black/30 2xl:h-1">
            {v != null && fill != null && (
              <span
                className={`block h-full rounded-full ${v >= 0 ? "bg-emerald-300 shadow-[0_0_4px_rgb(110_231_183/0.8)]" : "bg-rose-300 shadow-[0_0_4px_rgb(253_164_175/0.8)]"}`}
                style={{ width: `${fill * 100}%` }}
              />
            )}
          </span>
        )
      })}
    </span>
  )
}
