import { useState } from "react"
import { ChartSkeleton } from "@/components/chart-skeleton"
import { PeriodSelector } from "@/components/period-selector"
import { usePortfolioIndex, usePortfolioPerformers } from "@/lib/queries"
import { formatChangePct, changeColor } from "@/lib/format"
import { PortfolioChart } from "./portfolio-chart"
import { PerformersSection } from "./performers-section"

export function PortfolioPage() {
  const [period, setPeriod] = useState<string>("1y")
  const { data, isLoading, isFetching } = usePortfolioIndex(period)
  const { data: performers, isLoading: performersLoading } = usePortfolioPerformers(period)

  return (
    <div className="p-6 space-y-8">
      <div className="flex justify-center">
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      {isLoading ? (
        <ChartSkeleton height={480} />
      ) : !data || !data.dates.length ? (
        <div className="h-[480px] flex items-center justify-center text-muted-foreground">
          No data yet. Add assets to a group and refresh prices.
        </div>
      ) : (
        <div className="relative">
          {isFetching && (
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary/20 overflow-hidden z-10 rounded-t-md">
              <div className="h-full w-1/3 bg-primary animate-[slide_1s_ease-in-out_infinite]" />
            </div>
          )}
          <PortfolioChart dates={data.dates} values={data.values} up={data.change >= 0} />
          <ValueDisplay current={data.current} change={data.change} changePct={data.change_pct} />
        </div>
      )}

      <PerformersSection performers={performers} isLoading={performersLoading} period={period} />
    </div>
  )
}

function ValueDisplay({ current, change, changePct }: { current: number; change: number; changePct: number }) {
  const sign = change >= 0 ? "+" : ""
  const colorClass = changeColor(change)
  const chg = formatChangePct(changePct)

  return (
    <div className="text-center space-y-1">
      <div className="text-5xl font-light tracking-tight tabular-nums">
        {current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className={`text-sm font-medium ${colorClass} flex items-center justify-center gap-3`}>
        <span>{sign}{change.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span>{chg.text}</span>
      </div>
    </div>
  )
}
