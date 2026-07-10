import { useMemo, useState } from "react"
import { ChevronsDownUp, ChevronsUpDown, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useTheses, useThesesPerformance, useIndicators } from "@/lib/queries"
import { useQuotes } from "@/lib/quote-stream"
import { useSettings } from "@/lib/settings"
import type { Thesis, ThesisPerformancePoint } from "@/lib/api"
import { GroupTable } from "@/components/group-table"
import { ThesisSectionHeader } from "@/components/thesis/thesis-section-header"
import { ThesisMemberContextMenuContent } from "@/components/thesis/thesis-member-context-menu"
import { CrosshairTimeSyncProvider } from "@/components/chart/crosshair-time-sync"
import { EditThesisDialog } from "@/components/thesis/edit-thesis-dialog"

export function ThesesPage() {
  const { data: theses, isLoading } = useTheses()
  const { data: performance } = useThesesPerformance()
  const quotes = useQuotes()
  const { settings } = useSettings()

  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [showPlayedOut, setShowPlayedOut] = useState(false)
  const [editThesis, setEditThesis] = useState<Thesis | null>(null)

  const perfById = useMemo(() => {
    const map = new Map<number, ThesisPerformancePoint[]>()
    for (const s of performance ?? []) map.set(s.thesis_id, s.points)
    return map
  }, [performance])

  const allTheses = useMemo(() => theses ?? [], [theses])
  const hiddenPlayedOut = useMemo(
    () => allTheses.filter((t) => t.status === "played_out").length,
    [allTheses],
  )

  // Visible theses, sorted as a leaderboard: best aggregate first, nulls last.
  const visible = useMemo(() => {
    const filtered = showPlayedOut ? allTheses : allTheses.filter((t) => t.status !== "played_out")
    return [...filtered].sort((a, b) => {
      if (a.aggregate_pct == null && b.aggregate_pct == null) return 0
      if (a.aggregate_pct == null) return 1
      if (b.aggregate_pct == null) return -1
      return b.aggregate_pct - a.aggregate_pct
    })
  }, [allTheses, showPlayedOut])

  // Fetch indicators only for the members of expanded theses (lazy on expand).
  const expandedSymbols = useMemo(() => {
    const syms = new Set<string>()
    for (const t of visible) {
      if (!expanded.has(t.id)) continue
      for (const a of t.assets) syms.add(a.symbol)
    }
    return [...syms]
  }, [visible, expanded])
  const { data: indicators } = useIndicators(expandedSymbols)

  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const allExpanded = visible.length > 0 && visible.every((t) => expanded.has(t.id))
  const toggleAll = () => setExpanded(allExpanded ? new Set() : new Set(visible.map((t) => t.id)))

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Theses</h1>
        <div className="flex items-center gap-1">
          {(hiddenPlayedOut > 0 || showPlayedOut) && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-muted-foreground"
              onClick={() => setShowPlayedOut((v) => !v)}
            >
              {showPlayedOut ? "Hide played-out" : `Show played-out (${hiddenPlayedOut})`}
            </Button>
          )}
          {visible.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs text-muted-foreground"
              onClick={toggleAll}
            >
              {allExpanded ? (
                <ChevronsDownUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronsUpDown className="h-3.5 w-3.5" />
              )}
              {allExpanded ? "Collapse all" : "Expand all"}
            </Button>
          )}
        </div>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}

      {theses && visible.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
          <p>
            {allTheses.length === 0
              ? "No theses yet. Create one from a group's by-thesis view."
              : "No active theses — everything is played out. Use “Show played-out” to see them."}
          </p>
        </div>
      )}

      <CrosshairTimeSyncProvider enabled={true}>
        <div className="space-y-3">
          {visible.map((thesis) => {
            const isOpen = expanded.has(thesis.id)
            const members = thesis.assets
            return (
              <section key={thesis.id} className="rounded-md border border-border p-2">
                <ThesisSectionHeader
                  thesis={thesis}
                  expanded={isOpen}
                  onToggle={() => toggle(thesis.id)}
                  memberCount={thesis.assets.length}
                  performance={perfById.get(thesis.id)}
                  contextActions={[
                    { label: "Edit thesis…", action: () => setEditThesis(thesis), icon: Pencil },
                  ]}
                  actions={
                    <button
                      type="button"
                      onClick={() => setEditThesis(thesis)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      title="Edit thesis"
                      aria-label={`Edit ${thesis.name}`}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  }
                />
                {isOpen && (
                  <div className="mt-2 space-y-1">
                    {members.length > 0 ? (
                      <GroupTable
                        assets={members}
                        quotes={quotes}
                        indicators={indicators}
                        compactMode={settings.compact_mode}
                        renderContextMenu={({ asset, openEdit, openNewThesis }) => (
                          <ThesisMemberContextMenuContent
                            thesisId={thesis.id}
                            assetId={asset.id}
                            symbol={asset.symbol}
                            onEdit={openEdit}
                            onNewThesis={openNewThesis}
                          />
                        )}
                      />
                    ) : (
                      <p className="px-2 py-3 text-sm text-muted-foreground">
                        No members yet.
                      </p>
                    )}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      </CrosshairTimeSyncProvider>

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
