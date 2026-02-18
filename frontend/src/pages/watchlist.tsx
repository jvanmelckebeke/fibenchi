import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowDownAZ, ArrowUpAZ, LayoutGrid, Pencil, Table, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { AddSymbolDialog } from "@/components/add-symbol-dialog"
import { AssetActionMenu } from "@/components/asset-action-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { useGroup, useGroupSparklines, useGroupIndicators, useRemoveAssetFromGroup, useUpdateGroup, useTags, usePrefetchAssetDetail } from "@/lib/queries"
import { useQuotes } from "@/lib/quote-stream"
import { SparklineChart } from "@/components/sparkline"
import { RsiGauge } from "@/components/rsi-gauge"
import { MacdIndicator } from "@/components/macd-indicator"
import { TagBadge } from "@/components/tag-badge"
import type { AssetType, Quote, TagBrief, SparklinePoint, IndicatorSummary } from "@/lib/api"
import { formatPrice } from "@/lib/format"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useSettings, type AssetTypeFilter, type WatchlistSortBy, type SortDir } from "@/lib/settings"
import { useFilteredSortedAssets } from "@/lib/use-watchlist-filter"
import { WatchlistTable } from "@/components/watchlist-table"

const SORT_OPTIONS: [WatchlistSortBy, string][] = [
  ["name", "Name"],
  ["price", "Price"],
  ["change_pct", "Change %"],
  ["rsi", "RSI"],
  ["macd", "MACD"],
  ["macd_signal", "Signal"],
  ["macd_hist", "MACD Hist"],
]

const SORT_LABELS: Record<WatchlistSortBy, string> = Object.fromEntries(SORT_OPTIONS) as Record<WatchlistSortBy, string>

export function WatchlistPage({ groupId }: { groupId: number }) {
  const { data: group, isLoading: groupLoading } = useGroup(groupId)
  const { data: allTags } = useTags()
  const removeFromGroup = useRemoveAssetFromGroup()
  const [selectedTags, setSelectedTags] = useState<number[]>([])
  const [sparklinePeriod, setSparklinePeriod] = useState("3mo")
  const { settings, updateSettings } = useSettings()
  const viewMode = settings.watchlist_view_mode
  const setViewMode = (v: "card" | "table") => updateSettings({ watchlist_view_mode: v })
  const { data: batchSparklines } = useGroupSparklines(groupId, sparklinePeriod)
  const { data: batchIndicators } = useGroupIndicators(groupId)
  const prefetch = usePrefetchAssetDetail(settings.chart_default_period)

  const typeFilter = settings.watchlist_type_filter
  const sortBy = settings.watchlist_sort_by
  const sortDir = settings.watchlist_sort_dir

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
    updateSettings({ watchlist_type_filter: v })

  const handleSort = (key: WatchlistSortBy) => {
    if (sortBy === key) {
      updateSettings({ watchlist_sort_dir: sortDir === "asc" ? "desc" : "asc" })
    } else {
      const defaultDir: SortDir = key === "name" ? "asc" : "desc"
      updateSettings({ watchlist_sort_by: key, watchlist_sort_dir: defaultDir })
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
            value={viewMode}
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

      {viewMode === "table" && assets && assets.length > 0 ? (
        <WatchlistTable
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
              showSparkline={settings.watchlist_show_sparkline}
              showRsi={settings.watchlist_show_rsi}
              showMacd={settings.watchlist_show_macd}
            />
          ))}
        </div>
      )}
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

function AssetCard({
  symbol,
  name,
  type,
  currency,
  tags,
  quote,
  sparklinePeriod,
  sparklineData,
  indicatorData,
  onDelete,
  onHover,
  showSparkline,
  showRsi,
  showMacd,
}: {
  symbol: string
  name: string
  type: AssetType
  currency: string
  tags: TagBrief[]
  quote?: Quote
  sparklinePeriod: string
  sparklineData?: SparklinePoint[]
  indicatorData?: IndicatorSummary
  onDelete: () => void
  onHover: () => void
  showSparkline: boolean
  showRsi: boolean
  showMacd: boolean
}) {
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeColor =
    changePct != null ? (changePct >= 0 ? "text-green-500" : "text-red-500") : "text-muted-foreground"

  const [priceRef, pctRef] = usePriceFlash(lastPrice)

  return (
    <Card className="group relative hover:border-primary/50 transition-colors" onMouseEnter={onHover}>
      <AssetActionMenu
        onDelete={onDelete}
        triggerClassName="absolute right-2 top-2 h-7 w-7 opacity-0 group-hover:opacity-100 z-10"
      />
      <Link to={`/asset/${symbol}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <MarketStatusDot marketState={quote?.market_state} />
            <CardTitle className="text-base">{symbol}</CardTitle>
            <Badge variant="secondary" className="text-xs">
              {type}
            </Badge>
            {lastPrice != null ? (
              <span ref={priceRef} className="ml-auto text-base font-semibold tabular-nums rounded px-1 -mx-1">
                {formatPrice(lastPrice, currency)}
              </span>
            ) : (
              <Skeleton className="ml-auto h-5 w-16 rounded" />
            )}
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground truncate">{name}</p>
            {changePct != null ? (
              <span ref={pctRef} className={`text-xs font-medium tabular-nums rounded px-1 -mx-1 ${changeColor}`}>
                {changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
            ) : (
              <Skeleton className="h-3.5 w-12 rounded" />
            )}
          </div>
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {tags.map((tag) => (
                <TagBadge key={tag.id} name={tag.name} color={tag.color} />
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          {showSparkline && <SparklineChart symbol={symbol} period={sparklinePeriod} batchData={sparklineData} />}
          {(showRsi || showMacd) && (
            <div className="flex gap-1.5 mt-1">
              {showRsi && <RsiGauge symbol={symbol} batchRsi={indicatorData?.rsi} />}
              {showMacd && <MacdIndicator symbol={symbol} batchMacd={indicatorData ? { macd: indicatorData.macd, macd_signal: indicatorData.macd_signal, macd_hist: indicatorData.macd_hist } : undefined} />}
            </div>
          )}
        </CardContent>
      </Link>
    </Card>
  )
}
