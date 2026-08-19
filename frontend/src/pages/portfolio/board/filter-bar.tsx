import { SegmentedControl } from "@/components/ui/segmented-control"
import { type ColorMode } from "./color-scale"
import type { GroupBy, PhaseFilter } from "./use-board-data"

export function FilterBar({
  groupBy,
  onGroupBy,
  mode,
  onMode,
  phaseFilter,
  onPhaseFilter,
  coverage,
}: {
  groupBy: GroupBy
  onGroupBy: (v: GroupBy) => void
  mode: ColorMode
  onMode: (v: ColorMode) => void
  phaseFilter: PhaseFilter
  onPhaseFilter: (v: PhaseFilter) => void
  coverage: { total: number; scored: number; open: number }
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        Group by
        <SegmentedControl<GroupBy>
          options={[
            { value: "group", label: "Group" },
            { value: "thesis", label: "Thesis" },
          ]}
          value={groupBy}
          onChange={onGroupBy}
        />
      </span>
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        Colour by
        {/* Both modes are single-session measures: σ-Move is today's move in
            vol units, % is today's raw move. The multi-day windows belong to
            the Movers card, which owns its own selector. */}
        <SegmentedControl<ColorMode>
          options={[
            { value: "sigma", label: "σ-Move" },
            { value: "pct", label: "% today" },
          ]}
          value={mode}
          onChange={onMode}
        />
      </span>
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        Show
        {/* Open collapses the grid onto what can still move. Through most of
            the day the live names are a minority scattered across every
            section, so hiding beats dimming: dimming leaves them just as far
            apart. */}
        <SegmentedControl<PhaseFilter>
          options={[
            { value: "all", label: "All" },
            { value: "open", label: "Open" },
          ]}
          value={phaseFilter}
          onChange={onPhaseFilter}
        />
      </span>
      <span className="ml-auto rounded-full border border-border px-2.5 py-0.5 text-[11px] tabular-nums text-muted-foreground">
        {coverage.open} open · {coverage.scored} of {coverage.total} scored
      </span>
    </div>
  )
}
