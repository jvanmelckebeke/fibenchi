import { useMemo } from "react"
import { computeMovementStats } from "@/lib/movement-stats"
import { formatChangePct, changeColor, formatAssetPrice, formatDateLong } from "@/lib/format"
import type { Price, Asset } from "@/lib/types"

interface MovementStatsProps {
  prices: Price[]
  label: string
  symbol: string
  asset?: Asset
}

export function MovementStats({ prices, label, symbol, asset }: MovementStatsProps) {
  const stats = useMemo(() => computeMovementStats(prices), [prices])
  if (!stats) return null

  const hints = asset ?? { type: "stock" as const, symbol, currency: "USD" }
  const ret = formatChangePct(stats.periodReturnPct)

  return (
    <div className="rounded-lg border bg-card px-4 py-3 text-card-foreground">
      <h3 className="mb-3 text-xs font-medium tracking-wider text-muted-foreground uppercase">
        Movement · {label}
      </h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile
          label="Period return"
          valueText={ret.text}
          valueClass={ret.className}
          sub={`${formatAssetPrice(stats.startClose, hints)} → ${formatAssetPrice(stats.endClose, hints)}`}
        />
        <StatTile
          label="Max drawdown"
          valueText={stats.maxDrawdown ? formatChangePct(stats.maxDrawdown.pct).text : "0.00%"}
          valueClass={stats.maxDrawdown ? "text-red-500" : "text-muted-foreground"}
          sub={
            stats.maxDrawdown
              ? `${formatDateLong(stats.maxDrawdown.peakDate)} → ${formatDateLong(stats.maxDrawdown.troughDate)}`
              : "no decline"
          }
        />
        <StatTile
          label="Max daily gain"
          valueText={stats.maxDailyGain ? formatChangePct(stats.maxDailyGain.pct).text : "—"}
          valueClass={changeColor(stats.maxDailyGain?.pct)}
          sub={stats.maxDailyGain ? formatDateLong(stats.maxDailyGain.date) : undefined}
        />
        <StatTile
          label="Max daily loss"
          valueText={stats.maxDailyLoss ? formatChangePct(stats.maxDailyLoss.pct).text : "—"}
          valueClass={changeColor(stats.maxDailyLoss?.pct)}
          sub={stats.maxDailyLoss ? formatDateLong(stats.maxDailyLoss.date) : undefined}
        />
        <StatTile
          label="Up / down days"
          valueText={`${stats.upDays} / ${stats.downDays}`}
          valueClass="text-foreground"
          sub={`${stats.tradingDays} sessions`}
        />
      </div>
    </div>
  )
}

function StatTile({
  label,
  valueText,
  valueClass,
  sub,
}: {
  label: string
  valueText: string | null
  valueClass: string
  sub?: string
}) {
  return (
    <div className="rounded-md bg-muted/40 px-3 py-2">
      <div className="text-[10px] tracking-wider text-muted-foreground uppercase">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${valueClass}`}>{valueText ?? "—"}</div>
      {sub && (
        <div className="mt-0.5 truncate text-[11px] text-muted-foreground tabular-nums">{sub}</div>
      )}
    </div>
  )
}
