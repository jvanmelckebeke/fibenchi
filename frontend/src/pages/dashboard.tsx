import { useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Trash2, TrendingUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useAssets, useCreateAsset, useDeleteAsset } from "@/lib/queries"
import { SparklineChart } from "@/components/sparkline"

export function DashboardPage() {
  const { data: assets, isLoading } = useAssets()
  const createAsset = useCreateAsset()
  const deleteAsset = useDeleteAsset()
  const [symbol, setSymbol] = useState("")

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate({ symbol: s }, { onSuccess: () => setSymbol("") })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Watchlist</h1>
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
  onDelete,
}: {
  symbol: string
  name: string
  type: string
  onDelete: () => void
}) {
  return (
    <Card className="group relative hover:border-primary/50 transition-colors">
      <Button
        variant="ghost"
        size="icon"
        className="absolute right-2 top-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => {
          e.preventDefault()
          onDelete()
        }}
      >
        <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
      </Button>
      <Link to={`/asset/${symbol}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">{symbol}</CardTitle>
            <Badge variant="secondary" className="text-xs">
              {type}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground truncate">{name}</p>
        </CardHeader>
        <CardContent className="pt-0">
          <SparklineChart symbol={symbol} />
        </CardContent>
      </Link>
    </Card>
  )
}
