import { useState } from "react"
import { Link } from "react-router-dom"
import { X } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { ChartSyncProvider } from "@/components/chart/chart-sync-provider"
import { SubChart } from "@/components/chart/sub-chart"
import { useAssetDetail } from "@/lib/queries"
import type { Asset } from "@/lib/api"

interface ScannerViewProps {
  assets: Asset[]
  descriptorId: string
  period: string
}

export function ScannerView({ assets, descriptorId, period }: ScannerViewProps) {
  const [hiddenSymbols, setHiddenSymbols] = useState<Set<string>>(new Set())

  const visibleAssets = assets.filter((a) => !hiddenSymbols.has(a.symbol))
  const hiddenAssets = assets.filter((a) => hiddenSymbols.has(a.symbol))

  const toggleHide = (symbol: string) => {
    setHiddenSymbols((prev) => {
      const next = new Set(prev)
      if (next.has(symbol)) next.delete(symbol)
      else next.add(symbol)
      return next
    })
  }

  return (
    <div className="space-y-2">
      {/* Symbol filter chips */}
      {hiddenAssets.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-muted-foreground">Hidden:</span>
          {hiddenAssets.map((a) => (
            <button
              key={a.symbol}
              onClick={() => toggleHide(a.symbol)}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
            >
              +{a.symbol}
            </button>
          ))}
          {hiddenAssets.length > 1 && (
            <button
              onClick={() => setHiddenSymbols(new Set())}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Show all
            </button>
          )}
        </div>
      )}

      {/* Scanner rows */}
      <div className="space-y-3">
        {visibleAssets.map((asset) => (
          <ScannerRow
            key={asset.symbol}
            symbol={asset.symbol}
            name={asset.name}
            descriptorId={descriptorId}
            period={period}
            onHide={() => toggleHide(asset.symbol)}
          />
        ))}
      </div>
    </div>
  )
}

interface ScannerRowProps {
  symbol: string
  name: string
  descriptorId: string
  period: string
  onHide: () => void
}

function ScannerRow({ symbol, name, descriptorId, period, onHide }: ScannerRowProps) {
  const { data: detail, isLoading } = useAssetDetail(symbol, period)
  const prices = detail?.prices
  const indicators = detail?.indicators

  if (isLoading || !prices?.length) {
    return (
      <div className="rounded-md border border-border p-3">
        <div className="flex items-center gap-2 mb-2">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-[120px] w-full rounded-md" />
      </div>
    )
  }

  return (
    <ChartSyncProvider prices={prices} indicators={indicators ?? []}>
      <div className="rounded-md border border-border p-3">
        <div className="flex items-center gap-2 mb-1">
          <Link
            to={`/asset/${symbol}`}
            className="text-sm font-semibold hover:underline"
          >
            {symbol}
          </Link>
          <span className="text-xs text-muted-foreground truncate">{name}</span>
          <button
            onClick={onHide}
            className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
            title={`Hide ${symbol}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <SubChart descriptorId={descriptorId} showLegend roundedClass="rounded-md" />
      </div>
    </ChartSyncProvider>
  )
}
