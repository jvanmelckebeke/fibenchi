import { useState, useTransition } from "react"
import { ArrowDownAZ, ArrowUpAZ, LayoutGrid, Pencil, Table, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { AddSymbolDialog } from "@/components/add-symbol-dialog"
import { AssetCard } from "@/components/asset-card"
import { TagBadge } from "@/components/tag-badge"
import { useGroup, useGroupSparklines, useGroupIndicators, useRemoveAssetFromGroup, useUpdateGroup, useTags, usePrefetchAssetDetail } from "@/lib/queries"
import { useQuotes } from "@/lib/quote-stream"
import { buildSortOptions } from "@/lib/indicator-registry"
import { useSettings, type AssetTypeFilter, type GroupSortBy, type SortDir } from "@/lib/settings"
import { useFilteredSortedAssets } from "@/lib/use-group-filter"
import { GroupTable } from "@/components/group-table"

const SORT_OPTIONS = buildSortOptions()

const SORT_LABELS: Record<string, string> = Object.fromEntries(SORT_OPTIONS)

export function GroupPage({ groupId }: { groupId: number }) {
  const { data: group, isLoading: groupLoading } = useGroup(groupId)
  const { data: allTags } = useTags()
  const removeFromGroup = useRemoveAssetFromGroup()
  const [selectedTags, setSelectedTags] = useState<number[]>([])
  const [sparklinePeriod, setSparklinePeriod] = useState("3mo")
  const { settings, updateSettings } = useSettings()
  const [isPending, startTransition] = useTransition()
  const [deferredViewMode, setDeferredViewMode] = useState(settings.group_view_mode)
  const viewMode = deferredViewMode
  const setViewMode = (v: "card" | "table") => {
    updateSettings({ group_view_mode: v })
    startTransition(() => {
      setDeferredViewMode(v)
    })
  }
  const { data: batchSparklines } = useGroupSparklines(groupId, sparklinePeriod)
  const { data: batchIndicators } = useGroupIndicators(groupId)
  const prefetch = usePrefetchAssetDetail(settings.chart_default_period)

  const typeFilter = settings.group_type_filter
  const sortBy = settings.group_sort_by
  const sortDir = settings.group_sort_dir

  const quotes = useQuotes()

  const allAssets = group?.assets
  const isDefaultGroup = group?.is_default ?? false

  const assets = useFilteredSortedAssets(allAssets, {
    typeFilter,
    selectedTags,
    sortBy,
    sortDir,
    quotes,
    indicators: batchIndicators,
  })

  const setTypeFilter = (v: AssetTypeFilter) =>
    updateSettings({ group_type_filter: v })

  const handleSort = (key: GroupSortBy) => {
    if (sortBy === key) {
      updateSettings({ group_sort_dir: sortDir === "asc" ? "desc" : "asc" })
    } else {
      const defaultDir: SortDir = key === "name" ? "asc" : "desc"
      updateSettings({ group_sort_by: key, group_sort_dir: defaultDir })
    }
  }

  const handleRemove = (symbol: string) => {
    const asset = allAssets?.find((a) => a.symbol === symbol)
    if (asset) removeFromGroup.mutate({ groupId, assetId: asset.id })
  }

  const toggleTag = (id: number) =>
    setSelectedTags((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <GroupHeader groupId={groupId} group={group} isDefaultGroup={isDefaultGroup} />
          {/* Type filter */}
          <SegmentedControl
            options={[
              { value: "all", label: "All" },
              { value: "stock", label: "Stocks" },
              { value: "etf", label: "ETFs" },
            ]}
            value={typeFilter}
            onChange={setTypeFilter}
          />
          {/* Sparkline period */}
          <SegmentedControl
            options={[
              { value: "3mo", label: "3M" },
              { value: "6mo", label: "6M" },
              { value: "1y", label: "1Y" },
            ]}
            value={sparklinePeriod}
            onChange={setSparklinePeriod}
          />
          {/* Sort */}
          <div className="flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5">
                  {sortDir === "asc" ? <ArrowUpAZ className="h-3.5 w-3.5" /> : <ArrowDownAZ className="h-3.5 w-3.5" />}
                  {SORT_LABELS[sortBy]}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                {SORT_OPTIONS.map(([key, label]) => (
                  <DropdownMenuItem key={key} onClick={() => handleSort(key)}>
                    {label}
                    {sortBy === key && (
                      <span className="ml-auto text-muted-foreground text-xs">
                        {sortDir === "asc" ? "\u2191" : "\u2193"}
                      </span>
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {/* View mode toggle */}
          <SegmentedControl
            options={[
              { value: "card", label: <LayoutGrid className="h-3.5 w-3.5" /> },
              { value: "table", label: <Table className="h-3.5 w-3.5" /> },
            ]}
            value={settings.group_view_mode}
            onChange={setViewMode}
          />
        </div>
        <AddSymbolDialog groupId={groupId} isDefaultGroup={isDefaultGroup} />
      </div>

      {allTags && allTags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {allTags.map((tag) => (
            <TagBadge
              key={tag.id}
              name={tag.name}
              color={tag.color}
              active={selectedTags.length === 0 || selectedTags.includes(tag.id)}
              onClick={() => toggleTag(tag.id)}
            />
          ))}
          {selectedTags.length > 0 && (
            <button
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setSelectedTags([])}
            >
              Clear
            </button>
          )}
        </div>
      )}

      {groupLoading && <p className="text-muted-foreground">Loading...</p>}

      {assets && assets.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <TrendingUp className="h-12 w-12 mb-4" />
          <p>
            {allAssets && allAssets.length > 0
              ? "No assets match the current filters."
              : "No assets yet. Add a symbol above to get started."}
          </p>
        </div>
      )}

      <div className={isPending ? "opacity-70 transition-opacity" : "transition-opacity"}>
      {viewMode === "table" && assets && assets.length > 0 ? (
        <GroupTable
          assets={assets}
          quotes={quotes}
          indicators={batchIndicators}
          onDelete={handleRemove}
          compactMode={settings.compact_mode}
          onHover={prefetch}
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={handleSort}
        />
      ) : (
        <div className={`grid gap-4 ${
          settings.compact_mode
            ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5"
            : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        }`}>
          {assets?.map((asset) => (
            <AssetCard
              key={asset.id}
              symbol={asset.symbol}
              name={asset.name}
              type={asset.type}
              currency={asset.currency}
              tags={asset.tags}
              quote={quotes[asset.symbol]}
              sparklinePeriod={sparklinePeriod}
              sparklineData={batchSparklines?.[asset.symbol]}
              indicatorData={batchIndicators?.[asset.symbol]}
              onDelete={() => handleRemove(asset.symbol)}
              onHover={() => prefetch(asset.symbol)}
              showSparkline={settings.group_show_sparkline}
              indicatorVisibility={settings.group_indicator_visibility}
            />
          ))}
        </div>
      )}
      </div>
    </div>
  )
}

function GroupHeader({ groupId, group, isDefaultGroup }: {
  groupId: number
  group?: { name: string; description: string | null; assets: { id: number }[] }
  isDefaultGroup: boolean
}) {
  const updateGroup = useUpdateGroup()
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState("")

  const startEditing = () => {
    if (isDefaultGroup || !group) return
    setEditName(group.name)
    setEditing(true)
  }

  const saveEdit = () => {
    const name = editName.trim()
    if (!name || name === group?.name) {
      setEditing(false)
      return
    }
    updateGroup.mutate(
      { id: groupId, data: { name } },
      { onSuccess: () => setEditing(false) },
    )
  }

  if (!group) {
    return <Skeleton className="h-8 w-40" />
  }

  if (editing) {
    return (
      <Input
        value={editName}
        onChange={(e) => setEditName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") saveEdit()
          if (e.key === "Escape") setEditing(false)
        }}
        onBlur={saveEdit}
        autoFocus
        className="h-9 w-48 text-xl font-bold"
      />
    )
  }

  return (
    <div className="flex items-center gap-2">
      <h1 className="text-2xl font-bold">{group.name}</h1>
      {!isDefaultGroup && (
        <button
          onClick={startEditing}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Rename group"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
      )}
      <span className="text-sm text-muted-foreground">
        {group.assets.length} {group.assets.length === 1 ? "asset" : "assets"}
      </span>
    </div>
  )
}
