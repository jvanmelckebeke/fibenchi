import { useMemo } from "react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { RAMP_COLORS, sigmaUnit } from "./color-scale"
import type { ColorMode, PctWindow } from "./color-scale"
import { pctWindowDef } from "./color-scale"
import { BoardTile } from "./tile"
import type { BoardSection } from "./use-board-data"

export function Board({
  sections,
  mode,
  window,
}: {
  sections: BoardSection[]
  mode: ColorMode
  window: PctWindow
}) {
  // Day-adaptive σ scale: computed over the whole board so every section
  // shares one ramp (per-section scales would make colours incomparable).
  const unit = useMemo(
    () =>
      sigmaUnit(
        sections
          .flatMap((s) => s.tiles)
          .map((t) => t.sigma)
          .filter((v): v is number => v != null),
      ),
    [sections],
  )
  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-5">
        {sections.map((s) => (
          <section key={s.key}>
            <h2 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
              {s.accent && (
                <span aria-hidden className="h-4 w-[3px] rounded-full" style={{ backgroundColor: s.accent }} />
              )}
              {s.title}
              <span className="opacity-60">{s.tiles.length}</span>
            </h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(118px,1fr))] gap-1">
              {s.tiles.map((t) => (
                <BoardTile key={t.symbol} tile={t} mode={mode} window={window} unit={unit} />
              ))}
            </div>
          </section>
        ))}
        <Legend mode={mode} window={window} unit={unit} />
      </div>
    </TooltipProvider>
  )
}

function Legend({ mode, window, unit: sigmaScale }: { mode: ColorMode; window: PctWindow; unit: number }) {
  const unit = mode === "sigma" ? "σ" : "%"
  const scale = mode === "sigma" ? sigmaScale : pctWindowDef(window).maxAbs / 3
  const fmt = (n: number) => {
    const v = n * scale
    return Number.isInteger(v) ? `${v}` : v.toFixed(1)
  }
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="tabular-nums">-{fmt(3)}{unit}</span>
        <span
          className="h-3 w-36 rounded-[2px]"
          style={{ background: `linear-gradient(to right, ${RAMP_COLORS.join(", ")})` }}
        />
        <span className="tabular-nums">+{fmt(3)}{unit}</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="board-tile-unread h-3 w-5 rounded-[2px]" />
        no reading
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-[7px] w-[7px] rounded-full bg-cyan-400 ring-[1.5px] ring-white/80" /> open
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-[7px] w-[7px] rounded-full bg-amber-400 ring-[1.5px] ring-white/80" /> pre / post
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-[7px] w-[7px] rounded-full bg-zinc-800 ring-[1.5px] ring-white/60" /> closed
      </span>
    </div>
  )
}
