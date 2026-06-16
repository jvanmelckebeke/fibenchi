import { useMemo, useState } from "react"
import { ChevronDown, ChevronRight, Pencil, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Asset, Group, IndicatorSummary, Quote, Thesis, ThesisStatus } from "@/lib/api"
import type { GroupSortBy, SortDir } from "@/lib/settings"
import { formatChangePct, formatDateLong } from "@/lib/format"
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
  const [revealed, setRevealed] = useState<Set<number>>(new Set())
  const [newThesisOpen, setNewThesisOpen] = useState(false)
  const [editThesis, setEditThesis] = useState<Thesis | null>(null)

  const toggleReveal = (id: number) =>
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

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

  const currentIds = useMemo(() => new Set(assets.map((a) => a.id)), [assets])

  // Sections: one per thesis with >=1 member in THIS group, preserving the
  // incoming sort order within each section. A ticker in several theses appears
  // under each. "Ungrouped" collects this group's thesis-less assets.
  const { sections, ungrouped } = useMemo(() => {
    const memberOfAnyThesis = new Set<number>()
    const sections = theses.map((thesis) => {
      const memberIds = new Set(thesis.assets.map((m) => m.id))
      thesis.assets.forEach((m) => memberOfAnyThesis.add(m.id))
      const inGroup = assets.filter((a) => memberIds.has(a.id))
      const elsewhere = thesis.assets.filter((m) => !currentIds.has(m.id))
      return { thesis, inGroup, elsewhere }
    }).filter((s) => s.inGroup.length > 0)

    const ungrouped = assets.filter((a) => !memberOfAnyThesis.has(a.id))
    return { sections, ungrouped }
  }, [theses, assets, currentIds])

  const passthrough = {
    groupId, quotes, indicators, onDelete, compactMode, onHover, sortBy, sortDir, onSort,
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
        const isOpen = revealed.has(thesis.id)
        const elsewhereGroups = [
          ...new Set(elsewhere.flatMap((m) => otherGroupNamesById.get(m.id) ?? [])),
        ]
        const agg = formatChangePct(thesis.aggregate_pct)
        return (
          <section key={thesis.id} className="space-y-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: thesis.color }}
                aria-hidden
              />
              <h3 className="font-semibold">{thesis.name}</h3>
              <StatusBadge status={thesis.status} />
              <span className="text-xs text-muted-foreground">
                opened {formatDateLong(thesis.opened_at)}
              </span>
              {agg.text && (
                <span className={`text-sm font-medium ${agg.className}`} title="Equal-weight return since opened">
                  {agg.text}
                </span>
              )}
              <span className="text-xs text-muted-foreground">
                {inGroup.length} here
              </span>
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

            <GroupTable assets={inGroup} {...passthrough} />

            {elsewhere.length > 0 && (
              <div className="text-xs">
                <button
                  type="button"
                  onClick={() => toggleReveal(thesis.id)}
                  className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  +{elsewhere.length} more
                  {elsewhereGroups.length > 0 && <> in {elsewhereGroups.join(", ")}</>}
                </button>
                {isOpen && (
                  <ul className="mt-1 ml-4 space-y-0.5">
                    {elsewhere.map((m) => {
                      const where = otherGroupNamesById.get(m.id) ?? []
                      return (
                        <li key={m.id} className="text-muted-foreground">
                          <span className="font-medium text-foreground">{m.symbol}</span>
                          {" — "}{m.name}
                          {where.length > 0 && (
                            <span className="text-muted-foreground"> · in {where.join(", ")}</span>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            )}
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
