// The homepage dense board: every tracked asset as a σ-Move-coloured tile in
// one screen, with a rail of summary cards. Replaces the old index-chart +
// 1y-performers Overview (a history page, not a today page). Design spec:
// GitHub epic #512.

import { useMemo, useState } from "react"
import { Board } from "./board/board"
import { FilterBar } from "./board/filter-bar"
import { IndexCard, MoversCard, MostUnusualCard } from "./board/rail"
import type { ColorMode, PctWindow } from "./board/color-scale"
import { useBoardData, type GroupBy } from "./board/use-board-data"

// View prefs persist locally — they're device-level ergonomics, not data.
function usePersisted<T extends string>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => (localStorage.getItem(key) as T) ?? initial)
  const set = (v: T) => {
    setValue(v)
    localStorage.setItem(key, v)
  }
  return [value, set] as const
}

export function PortfolioPage() {
  const [groupBy, setGroupBy] = usePersisted<GroupBy>("board-group-by", "group")
  const [mode, setMode] = usePersisted<ColorMode>("board-color-mode", "sigma")
  const [window, setWindow] = usePersisted<PctWindow>("board-pct-window", "1wk")
  const { sections, tiles, coverage, isLoading } = useBoardData(groupBy)
  const allTiles = useMemo(() => [...tiles.values()], [tiles])

  return (
    <div className="flex flex-col gap-5 p-4 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1 space-y-4">
        <FilterBar
          groupBy={groupBy}
          onGroupBy={setGroupBy}
          mode={mode}
          onMode={setMode}
          window={window}
          onWindow={setWindow}
          coverage={coverage}
        />
        {isLoading ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-1">
            {Array.from({ length: 24 }, (_, i) => (
              <div key={i} className="h-[80px] animate-pulse rounded-[3px] bg-muted/40" />
            ))}
          </div>
        ) : sections.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted-foreground">
            No assets yet. Add assets to a group and refresh prices.
          </p>
        ) : (
          <Board sections={sections} mode={mode} window={window} />
        )}
      </div>
      <aside className="w-full shrink-0 space-y-3 lg:w-[300px]">
        <IndexCard />
        <MoversCard tiles={allTiles} />
        <MostUnusualCard tiles={allTiles} />
      </aside>
    </div>
  )
}
