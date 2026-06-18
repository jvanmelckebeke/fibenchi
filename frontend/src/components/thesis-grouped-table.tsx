import { useMemo, useState } from "react"
import { Pencil, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Asset, Group, IndicatorSummary, Quote, Thesis, ThesisStatus } from "@/lib/api"
import type { GroupSortBy, SortDir } from "@/lib/settings"
import { formatChangePct, formatDateLong, readableTextColor } from "@/lib/format"
import { resolveIcon } from "@/lib/icon-utils"
import { useIndicators } from "@/lib/queries"
import { GroupTable } from "@/components/group-table"
import { NewThesisDialog } from "@/components/new-thesis-dialog"
import { EditThesisDialog } from "@/components/edit-thesis-dialog"

interface ThesisGroupedTableProps {
  groupId: number
  assets: Asset[]
  theses: Thesis[]
  allGroups: Group[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
  onDelete: (symbol: string) => void
  compactMode: boolean
  onHover?: (symbol: string) => void
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
}

const STATUS_STYLES: Record<ThesisStatus, { label: string; className: string }> = {
  live: { label: "Live", className: "bg-emerald-500/15 text-emerald-500" },
  watching: { label: "Watching", className: "bg-amber-500/15 text-amber-500" },
  played_out: { label: "Played out", className: "bg-muted text-muted-foreground" },
}

function StatusBadge({ status }: { status: ThesisStatus }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.watching
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${s.className}`}>
      {s.label}
    </span>
  )
}

export function ThesisGroupedTable({
  groupId, assets, theses, allGroups, quotes, indicators,
  onDelete, compactMode, onHover, sortBy, sortDir, onSort,
}: ThesisGroupedTableProps) {
  const [newThesisOpen, setNewThesisOpen] = useState(false)
  const [editThesis, setEditThesis] = useState<Thesis | null>(null)
  // Which theses have their "+N more" fold expanded (drives the lazy indicator fetch).
  const [revealed, setRevealed] = useState<Set<number>>(new Set())

  const toggleReveal = (id: number) =>
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // Full Asset objects keyed by id, sourced from every group. Lets the "elsewhere"
  // fold render the same rich GroupTable rows (price/change/indicators) as the
  // in-group section — thesis members only carry id/symbol/name.
  const assetsById = useMemo(() => {
    const map = new Map<number, Asset>()
    for (const g of allGroups) {
      for (const a of g.assets) {
        if (!map.has(a.id)) map.set(a.id, a)
      }
    }
    return map
  }, [allGroups])

  // Which other groups (by name) contain each asset — for the "+N more in [group]" fold.
  const otherGroupNamesById = useMemo(() => {
    const map = new Map<number, string[]>()
    for (const g of allGroups) {
      if (g.id === groupId) continue
      for (const a of g.assets) {
        const list = map.get(a.id)
        if (list) list.push(g.name)
        else map.set(a.id, [g.name])
      }
    }
    return map
  }, [allGroups, groupId])

  // Unfiltered membership of the current group: a thesis member that lives in
  // this group but is hidden by an active type/tag filter must NOT be counted as
  // living "elsewhere" (the filtered `assets` prop would misclassify it).
  const currentGroupIds = useMemo(() => {
    const g = allGroups.find((grp) => grp.id === groupId)
    return new Set((g?.assets ?? []).map((a) => a.id))
  }, [allGroups, groupId])

  // Sections: one per thesis with >=1 member in THIS group, preserving the
  // incoming sort order within each section. A ticker in several theses appears
  // under each. "Ungrouped" collects this group's thesis-less assets.
  const { sections, ungrouped } = useMemo(() => {
    const memberOfAnyThesis = new Set<number>()
    const sections = theses.map((thesis) => {
      const memberIds = new Set(thesis.assets.map((m) => m.id))
      thesis.assets.forEach((m) => memberOfAnyThesis.add(m.id))
      const inGroup = assets.filter((a) => memberIds.has(a.id))
      const elsewhere = thesis.assets.filter((m) => !currentGroupIds.has(m.id))
      return { thesis, inGroup, elsewhere }
    }).filter((s) => s.inGroup.length > 0)

    const ungrouped = assets.filter((a) => !memberOfAnyThesis.has(a.id))
    return { sections, ungrouped }
  }, [theses, assets, currentGroupIds])

  // Symbols of elsewhere-members for theses whose fold is open. Fetched lazily so
  // expanding a fold (not just rendering the view) is what triggers the request.
  const expandedElsewhereSymbols = useMemo(() => {
    const syms = new Set<string>()
    for (const { thesis, elsewhere } of sections) {
      if (!revealed.has(thesis.id)) continue
      for (const m of elsewhere) {
        const a = assetsById.get(m.id)
        if (a) syms.add(a.symbol)
      }
    }
    return [...syms]
  }, [sections, revealed, assetsById])

  const { data: elsewhereIndicators } = useIndicators(expandedElsewhereSymbols)

  // The per-group batch (`indicators`) only covers in-group assets; merge in the
  // symbol-addressed snapshots so elsewhere rows get RSI/MACD/ATR/… too. Overlapping
  // symbols carry identical values, so precedence is irrelevant.
  const mergedIndicators = useMemo(
    () => ({ ...(elsewhereIndicators ?? {}), ...(indicators ?? {}) }),
    [elsewhereIndicators, indicators],
  )

  const passthrough = {
    groupId, quotes, indicators: mergedIndicators, onDelete, compactMode, onHover, sortBy, sortDir, onSort,
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-1.5 text-xs"
          onClick={() => setNewThesisOpen(true)}
        >
          <Plus className="h-3.5 w-3.5" />
          New thesis
        </Button>
      </div>

      {sections.map(({ thesis, inGroup, elsewhere }) => {
        const elsewhereGroups = [
          ...new Set(elsewhere.flatMap((m) => otherGroupNamesById.get(m.id) ?? [])),
        ]
        const agg = formatChangePct(thesis.aggregate_pct)
        const elsewhereAssets = elsewhere
          .map((m) => assetsById.get(m.id))
          .filter((a): a is Asset => a != null)
        const moreLabel = (
          <>
            +{elsewhereAssets.length} more
            {elsewhereGroups.length > 0 && <> in {elsewhereGroups.join(", ")}</>}
          </>
        )
        const ThesisIcon = resolveIcon(thesis.icon ?? "lightbulb")
        return (
          <section key={thesis.id} className="space-y-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                style={{ backgroundColor: thesis.color }}
                aria-hidden
              >
                <ThesisIcon className="h-4 w-4" style={{ color: readableTextColor(thesis.color) }} />
              </span>
              <h3 className="font-semibold">{thesis.name}</h3>
              <StatusBadge status={thesis.status} />
              <span className="text-xs text-muted-foreground">
                opened {formatDateLong(thesis.opened_at)}
              </span>
              {agg.text && (
                <span className={`text-sm font-medium ${agg.className}`} title="Equal-weight return since opened, across all members (including any in other groups)">
                  {agg.text}
                </span>
              )}
              <button
                type="button"
                onClick={() => setEditThesis(thesis)}
                className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
                title="Edit thesis"
                aria-label={`Edit ${thesis.name}`}
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>

            <GroupTable
              assets={inGroup}
              moreAssets={elsewhereAssets}
              moreLabel={moreLabel}
              moreOpen={revealed.has(thesis.id)}
              onToggleMore={() => toggleReveal(thesis.id)}
              {...passthrough}
            />
          </section>
        )
      })}

      {ungrouped.length > 0 && (
        <section className="space-y-2">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-muted-foreground">Ungrouped</h3>
            <span className="text-xs text-muted-foreground">{ungrouped.length}</span>
          </div>
          <GroupTable assets={ungrouped} {...passthrough} />
        </section>
      )}

      <NewThesisDialog open={newThesisOpen} onOpenChange={setNewThesisOpen} />
      <EditThesisDialog
        thesis={editThesis}
        open={editThesis !== null}
        onOpenChange={(o) => {
          if (!o) setEditThesis(null)
        }}
      />
    </div>
  )
}
