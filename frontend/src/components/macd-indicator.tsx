import { Skeleton } from "@/components/ui/skeleton"
import type { IndicatorSummary } from "@/lib/api"

export function MacdIndicator({
  batchMacd,
}: {
  symbol: string
  batchMacd?: Pick<IndicatorSummary, "macd" | "macd_signal" | "macd_hist"> | null
}) {
  if (batchMacd === undefined) {
    return <Skeleton className="h-5 w-full rounded-full" />
  }

  if (batchMacd?.macd == null || batchMacd?.macd_signal == null || batchMacd?.macd_hist == null) {
    return (
      <div className="flex items-center justify-center h-5 rounded-full bg-muted text-[10px] text-muted-foreground">
        No MACD
      </div>
    )
  }

  const { macd, macd_signal: sig, macd_hist: hist } = batchMacd
  const histPositive = hist >= 0
  const bullish = macd > sig

  // Batch mode: no full series available, use a fixed proportion
  const barPct = 25

  const histColor = histPositive ? "bg-emerald-500/30" : "bg-red-500/30"
  const macdTextColor = bullish ? "text-emerald-400" : "text-red-400"
  const histTextColor = histPositive ? "text-emerald-400" : "text-red-400"

  return (
    <div className="relative h-5 w-full rounded-full bg-muted overflow-hidden flex items-center px-2">
      {/* Center line */}
      <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
      {/* Histogram fill */}
      <div
        className={`absolute top-0 h-full ${histColor}`}
        style={{
          left: histPositive ? "50%" : `${50 - barPct}%`,
          width: `${barPct}%`,
        }}
      />
      {/* Values inside bar */}
      <span className={`relative z-10 text-[10px] font-medium tabular-nums ${macdTextColor}`}>
        M {macd.toFixed(2)}
      </span>
      <span className="relative z-10 text-[10px] tabular-nums text-muted-foreground ml-1.5">
        S {sig.toFixed(2)}
      </span>
      <span className={`relative z-10 text-[10px] font-medium tabular-nums ml-auto ${histTextColor}`}>
        H {histPositive ? "+" : ""}{hist.toFixed(2)}
      </span>
    </div>
  )
}
