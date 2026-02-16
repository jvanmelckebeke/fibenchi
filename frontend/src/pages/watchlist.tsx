import { useState, useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import { ArrowDownAZ, ArrowUpAZ, LayoutGrid, MoreVertical, Plus, Table, Trash2, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Skeleton } from "@/components/ui/skeleton"
import { useAssets, useCreateAsset, useDeleteAsset, useTags, useWatchlistSparklines, useWatchlistIndicators, usePrefetchAssetDetail, useSymbolSearch } from "@/lib/queries"
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

export function WatchlistPage() {
  const { data: allAssets, isLoading } = useAssets()
  const { data: allTags } = useTags()
  const createAsset = useCreateAsset()
  const deleteAsset = useDeleteAsset()
  const [symbol, setSymbol] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedTags, setSelectedTags] = useState<number[]>([])
  const [sparklinePeriod, setSparklinePeriod] = useState("3mo")
  const { settings, updateSettings } = useSettings()
  const viewMode = settings.watchlist_view_mode
  const setViewMode = (v: "card" | "table") => updateSettings({ watchlist_view_mode: v })
  const { data: batchSparklines } = useWatchlistSparklines(sparklinePeriod)
  const { data: batchIndicators } = useWatchlistIndicators()
  const prefetch = usePrefetchAssetDetail(settings.chart_default_period)
  const { data: searchResults } = useSymbolSearch(debouncedQuery)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(symbol.trim()), 300)
    return () => clearTimeout(timer)
  }, [symbol])

  const typeFilter = settings.watchlist_type_filter
  const sortBy = settings.watchlist_sort_by
  const sortDir = settings.watchlist_sort_dir

  const watchlisted = allAssets?.filter((a) => a.watchlisted)
  const quotes = useQuotes()

  const assets = useFilteredSortedAssets(watchlisted, {
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

  const toggleTag = (id: number) =>
    setSelectedTags((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate(
      { symbol: s },
      {
        onSuccess: () => {
          setSymbol("")
          setDialogOpen(false)
        },
      },
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold">Watchlist</h1>
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
        <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setSymbol(""); setShowSuggestions(false); createAsset.reset() } }}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1.5">
              <Plus className="h-4 w-4" />
              Add Symbol
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add Symbol</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="relative">
                <Input
                  placeholder="Search by name or symbol (e.g. AAPL, Porsche)"
                  value={symbol}
                  onChange={(e) => { setSymbol(e.target.value); setShowSuggestions(true) }}
                  onKeyDown={(e) => { if (e.key === "Enter") { setShowSuggestions(false); handleAdd() } }}
                  onFocus={() => setShowSuggestions(true)}
                  autoFocus
                />
                {showSuggestions && searchResults && searchResults.length > 0 && symbol.trim() && (
                  <div
                    ref={suggestionsRef}
                    className="absolute z-50 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-md max-h-60 overflow-auto"
                  >
                    {searchResults.map((r) => (
                      <button
                        key={r.symbol}
                        type="button"
                        className="flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => { setSymbol(r.symbol); setShowSuggestions(false) }}
                      >
                        <span className="font-mono font-medium text-primary shrink-0">{r.symbol}</span>
                        <span className="text-muted-foreground truncate">{r.name}</span>
                        <Badge variant="secondary" className="ml-auto text-xs shrink-0">{r.exchange}</Badge>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {createAsset.isError && (
                <p className="text-sm text-destructive">{createAsset.error.message}</p>
              )}
              <div className="flex justify-end">
                <Button onClick={() => { setShowSuggestions(false); handleAdd() }} disabled={createAsset.isPending || !symbol.trim()}>
                  {createAsset.isPending ? "Adding…" : "Add"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
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

      {isLoading && <p className="text-muted-foreground">Loading...</p>}

      {assets && assets.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <TrendingUp className="h-12 w-12 mb-4" />
          <p>
            {watchlisted && watchlisted.length > 0
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
          onDelete={(s) => deleteAsset.mutate(s)}
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
              onDelete={() => deleteAsset.mutate(asset.symbol)}
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
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity z-10"
            onClick={(e) => e.preventDefault()}
          >
            <MoreVertical className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-48">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.preventDefault()
              onDelete()
            }}
          >
            <Trash2 className="h-3.5 w-3.5 mr-2" />
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Link to={`/asset/${symbol}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
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
