import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { HoldingsGrid, type HoldingsGridRow } from "@/components/holdings-grid"
import type { EtfHoldings } from "@/lib/api"
import { useEtfHoldings, useHoldingsIndicators } from "@/lib/queries"

export function HoldingsSection({ symbol }: { symbol: string }) {
  const { data, isLoading } = useEtfHoldings(symbol, true)
  const { data: indicators, isLoading: indicatorsLoading } = useHoldingsIndicators(symbol, !!data?.top_holdings.length)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card className="p-4">
          <Skeleton className="h-4 w-48 mb-3" />
          <div className="space-y-2">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-14" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <Skeleton className="h-4 w-36 mb-3" />
          <div className="space-y-2">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-3 rounded" style={{ width: `${80 - i * 10}%` }} />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    )
  }
  if (!data || (!data.top_holdings.length && !data.sector_weightings.length)) {
    return null
  }

  const indicatorMap = new Map((indicators ?? []).map((i) => [i.symbol, i]))

  return (
    <div className="space-y-6">
      <TopHoldingsCard data={data} indicatorMap={indicatorMap} indicatorsLoading={indicatorsLoading} />
      <SectorWeightingsCard data={data} />
    </div>
  )
}

function TopHoldingsCard({
  data,
  indicatorMap,
  indicatorsLoading,
}: {
  data: EtfHoldings
  indicatorMap: ReadonlyMap<string, { currency: string; close: number | null; change_pct: number | null; values: Record<string, number | string | null> }>
  indicatorsLoading: boolean
}) {
  const rows: HoldingsGridRow[] = data.top_holdings.map((h) => ({
    key: h.symbol,
    symbol: h.symbol,
    name: h.name,
    percent: h.percent,
  }))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">
        Top {data.top_holdings.length} Holdings ({data.total_percent}% of Total Assets)
      </h3>
      <HoldingsGrid
        rows={rows}
        indicatorMap={indicatorMap}
        indicatorsLoading={indicatorsLoading}
        linkTarget="_blank"
      />
    </Card>
  )
}

function SectorWeightingsCard({ data }: { data: EtfHoldings }) {
  if (!data.sector_weightings.length) return null
  const maxPct = Math.max(...data.sector_weightings.map((s) => s.percent))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Sector Weightings</h3>
      <div className="space-y-0">
        <div className="grid grid-cols-[1fr_6rem_3.5rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1">
          <span>Sector</span>
          <span></span>
          <span className="text-right">Weight</span>
        </div>
        {data.sector_weightings.map((s) => (
          <div key={s.sector} className="grid grid-cols-[1fr_6rem_3.5rem] text-sm py-1 items-center">
            <span className="text-xs">{s.sector}</span>
            <div className="h-3 bg-muted rounded overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded"
                style={{ width: `${(s.percent / maxPct) * 100}%` }}
              />
            </div>
            <span className="text-right font-medium text-xs">{s.percent.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
