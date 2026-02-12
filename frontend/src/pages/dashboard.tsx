import { useState } from "react"
import { Link } from "react-router-dom"
import { MoreVertical, Plus, Trash2, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useAssets, useCreateAsset, useDeleteAsset, useStaggeredQuotes, useTags } from "@/lib/queries"
import { SparklineChart } from "@/components/sparkline"
import { RsiGauge } from "@/components/rsi-gauge"
import { TagBadge } from "@/components/tag-badge"
import type { Quote, TagBrief } from "@/lib/api"
import { formatPrice } from "@/lib/format"

export function DashboardPage() {
  const { data: allAssets, isLoading } = useAssets()
  const { data: allTags } = useTags()
  const createAsset = useCreateAsset()
  const deleteAsset = useDeleteAsset()
  const [symbol, setSymbol] = useState("")
  const [selectedTags, setSelectedTags] = useState<number[]>([])
  const [sparklinePeriod, setSparklinePeriod] = useState("3mo")

  const watchlisted = allAssets?.filter((a) => a.watchlisted)
  const watchlistedSymbols = watchlisted?.map((a) => a.symbol) ?? []
  const quotes = useStaggeredQuotes(watchlistedSymbols)
  const assets = watchlisted?.filter((a) => {
    if (selectedTags.length === 0) return true
    return a.tags.some((t) => selectedTags.includes(t.id))
  })

  const toggleTag = (id: number) =>
    setSelectedTags((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate({ symbol: s }, { onSuccess: () => setSymbol("") })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold">Watchlist</h1>
          <div className="flex rounded-md border border-border overflow-hidden">
            {(["3mo", "6mo", "1y"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setSparklinePeriod(p)}
                className={`px-2.5 py-1 text-xs font-medium transition-colors ${
                  sparklinePeriod === p
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {p === "3mo" ? "3M" : p === "6mo" ? "6M" : "1Y"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="Add symbol (e.g. AAPL)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            className="w-48"
          />
          <Button onClick={handleAdd} disabled={createAsset.isPending} size="icon">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
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

      {createAsset.isError && (
        <p className="text-sm text-destructive">{createAsset.error.message}</p>
      )}

      {isLoading && <p className="text-muted-foreground">Loading...</p>}

      {assets && assets.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <TrendingUp className="h-12 w-12 mb-4" />
          <p>No assets yet. Add a symbol above to get started.</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
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
            onDelete={() => deleteAsset.mutate(asset.symbol)}
          />
        ))}
      </div>
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
  onDelete,
}: {
  symbol: string
  name: string
  type: string
  currency: string
  tags: TagBrief[]
  quote?: Quote
  sparklinePeriod: string
  onDelete: () => void
}) {
  const hasQuote = quote?.price != null
  const changePct = quote?.change_percent
  const changeColor =
    changePct != null ? (changePct >= 0 ? "text-green-500" : "text-red-500") : "text-muted-foreground"

  return (
    <Card className="group relative hover:border-primary/50 transition-colors">
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
            {hasQuote && (
              <span className="ml-auto text-base font-semibold tabular-nums">
                {formatPrice(quote!.price!, currency)}
              </span>
            )}
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground truncate">{name}</p>
            {changePct != null && (
              <span className={`text-xs font-medium tabular-nums ${changeColor}`}>
                {changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
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
          <SparklineChart symbol={symbol} currency={currency} period={sparklinePeriod} />
          <RsiGauge symbol={symbol} />
        </CardContent>
      </Link>
    </Card>
  )
}
