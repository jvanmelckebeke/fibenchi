import { useMemo } from "react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { RAMP_COLORS, pctSpan, sigmaUnit } from "./color-scale"
import type { ColorMode } from "./color-scale"
import { BoardTile, PhaseIcon } from "./tile"
import type { BoardSection } from "./use-board-data"

export function Board({ sections, mode }: { sections: BoardSection[]; mode: ColorMode }) {
  // Day-adaptive scale: computed over the whole board so every section
  // shares one ramp (per-section scales would make colours incomparable).
  const span = useMemo(() => {
    const tiles = sections.flatMap((s) => s.tiles)
    if (mode === "sigma")
      return 3 * sigmaUnit(tiles.map((t) => t.sigma).filter((v): v is number => v != null))
    return pctSpan(tiles.map((t) => t.todayPct).filter((v): v is number => v != null))
  }, [sections, mode])
  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-5">
        {sections.map((s) => (
          <section key={s.key}>
            <h2 className="mb-1.5 flex items-center gap-2 text-xs font-medium 2xl:mb-2 2xl:text-[13px] text-muted-foreground">
              {s.accent && (
                <span aria-hidden className="h-4 w-[3px] rounded-full" style={{ backgroundColor: s.accent }} />
              )}
              {s.title}
              <span className="opacity-60">{s.tiles.length}</span>
            </h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-[3px] 2xl:grid-cols-[repeat(auto-fill,minmax(140px,1fr))] 2xl:gap-1">
              {s.tiles.map((t) => (
                <BoardTile key={t.symbol} tile={t} mode={mode} span={span} />
              ))}
            </div>
          </section>
        ))}
        <Legend mode={mode} span={span} />
      </div>
    </TooltipProvider>
  )
}

function Legend({ mode, span }: { mode: ColorMode; span: number }) {
  const unit = mode === "sigma" ? "\u03c3" : "%"
  const fmt = () => (Number.isInteger(span) ? `${span}` : span.toFixed(1))
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="tabular-nums">-{fmt()}{unit}</span>
        <span
          className="h-3 w-36 rounded-[2px]"
          style={{ background: `linear-gradient(to right, ${RAMP_COLORS.join(", ")})` }}
        />
        <span className="tabular-nums">+{fmt()}{unit}</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="board-tile-unread h-3 w-5 rounded-[2px]" />
        no reading
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="open" /> open
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="premarket" /> pre
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="aftermarket" /> post
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="closed" /> closed
      </span>
    </div>
  )
}
