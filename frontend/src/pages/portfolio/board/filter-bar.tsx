import { SegmentedControl } from "@/components/ui/segmented-control"
import { PCT_WINDOWS, type ColorMode, type PctWindow } from "./color-scale"
import type { GroupBy } from "./use-board-data"

export function FilterBar({
  groupBy,
  onGroupBy,
  mode,
  onMode,
  window,
  onWindow,
  coverage,
}: {
  groupBy: GroupBy
  onGroupBy: (v: GroupBy) => void
  mode: ColorMode
  onMode: (v: ColorMode) => void
  window: PctWindow
  onWindow: (v: PctWindow) => void
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
        <SegmentedControl<ColorMode>
          options={[
            { value: "sigma", label: "σ-Move" },
            { value: "pct", label: "% change" },
          ]}
          value={mode}
          onChange={onMode}
        />
        {/* The window scopes the tiles and nothing else — it lives beside the
            control it scopes, and disappears in σ mode (σ-Move is a
            single-session measure; a multi-day σ isn't a thing vnr computes). */}
        {mode === "pct" && (
          <>
            over
            <SegmentedControl<PctWindow>
              options={PCT_WINDOWS.map((w) => ({ value: w.value, label: w.label }))}
              value={window}
              onChange={onWindow}
            />
          </>
        )}
      </span>
      <span className="ml-auto rounded-full border border-border px-2.5 py-0.5 text-[11px] tabular-nums text-muted-foreground">
        {coverage.open} open · {coverage.scored} of {coverage.total} scored
      </span>
    </div>
  )
}
