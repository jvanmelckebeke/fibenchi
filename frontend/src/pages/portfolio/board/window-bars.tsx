import { PCT_WINDOWS } from "./color-scale"
import type { Tile } from "./use-board-data"

// One track per window on a dark rail, filled from the left in proportion to
// the move against that window's maxAbs, so a quiet week is a short stub and a
// big month runs the full width. Pastel fill plus a soft glow keeps the sign
// readable over the tile's own green or red ramp. Numbers live in the tooltip.
const MIN_FILL = 0.12

export function WindowBars({ windowPct }: { windowPct: Tile["windowPct"] }) {
  return (
    <span aria-hidden className="flex gap-[3px]">
      {PCT_WINDOWS.map((w) => {
        const v = windowPct[w.value]
        const up = v != null && v >= 0
        const width = v == null ? 0 : Math.max(MIN_FILL, Math.min(1, Math.abs(v) / w.maxAbs))
        return (
          <span key={w.value} className="h-[3px] flex-1 overflow-hidden rounded-full bg-black/30 2xl:h-1">
            {v != null && (
              <span
                className={`block h-full rounded-full ${up ? "bg-emerald-300 shadow-[0_0_4px_rgb(110_231_183/0.8)]" : "bg-rose-300 shadow-[0_0_4px_rgb(253_164_175/0.8)]"}`}
                style={{ width: `${width * 100}%` }}
              />
            )}
          </span>
        )
      })}
    </span>
  )
}
