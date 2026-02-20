import { Link } from "react-router-dom"
import { Loader2, TrendingUp, TrendingDown } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { usePrefetchAssetDetail } from "@/lib/queries"
import { formatChangePct } from "@/lib/format"
import type { AssetPerformance } from "@/lib/api"

export function PerformersSection({
  performers,
  isLoading,
  period,
}: {
  performers: AssetPerformance[] | undefined
  isLoading: boolean
  period: string
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading performers...</span>
      </div>
    )
  }

  if (!performers?.length) return null

  const top5 = performers.slice(0, 5)
  const bottom5 = [...performers].reverse().slice(0, 5)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <PerformersList
        title="Top Performers"
        icon={<TrendingUp className="h-4 w-4 text-emerald-500" />}
        assets={top5}
        period={period}
      />
      <PerformersList
        title="Bottom Performers"
        icon={<TrendingDown className="h-4 w-4 text-red-500" />}
        assets={bottom5}
        period={period}
      />
    </div>
  )
}

function PerformersList({
  title,
  icon,
  assets,
  period,
}: {
  title: string
  icon: React.ReactNode
  assets: AssetPerformance[]
  period: string
}) {
  const prefetch = usePrefetchAssetDetail(period)

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="secondary" className="text-xs ml-auto">{period}</Badge>
      </div>
      <div className="space-y-0">
        {assets.map((a) => {
          const chg = formatChangePct(a.change_pct)
          return (
            <Link
              key={a.symbol}
              to={`/asset/${a.symbol}`}
              className="flex items-center justify-between py-2 hover:bg-muted/50 rounded px-2 -mx-2 transition-colors"
              onMouseEnter={() => prefetch(a.symbol)}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-mono text-sm text-primary">{a.symbol}</span>
                <span className="text-xs text-muted-foreground truncate">{a.name}</span>
              </div>
              <span className={`text-sm font-medium tabular-nums ${chg.className}`}>
                {chg.text}
              </span>
            </Link>
          )
        })}
      </div>
    </Card>
  )
}
