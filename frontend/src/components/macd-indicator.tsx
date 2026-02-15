import { Skeleton } from "@/components/ui/skeleton"
import { useIndicators } from "@/lib/queries"

function getSignalLabel(macd: number, signal: number): { text: string; className: string } {
  if (macd > signal) return { text: "Bullish", className: "text-emerald-500" }
  return { text: "Bearish", className: "text-red-500" }
}

export function MacdIndicator({ symbol }: { symbol: string }) {
  const { data: indicators, isLoading } = useIndicators(symbol)

  const latest = indicators
    ?.slice()
    .reverse()
    .find((i) => i.macd !== null && i.macd_signal !== null && i.macd_hist !== null)

  if (isLoading) {
    return (
      <div className="space-y-1">
        <Skeleton className="h-1.5 w-full rounded-full" />
        <Skeleton className="h-3 w-20 rounded" />
      </div>
    )
  }

  if (latest?.macd == null || latest?.macd_signal == null || latest?.macd_hist == null) {
    return (
      <div className="flex items-center justify-center h-5 text-[10px] text-muted-foreground">
        No MACD
      </div>
    )
  }

  const hist = latest.macd_hist
  const positive = hist >= 0
  const signal = getSignalLabel(latest.macd, latest.macd_signal)

  // Normalize histogram bar against recent range
  const recentHists = (indicators ?? [])
    .map((i) => i.macd_hist)
    .filter((v): v is number => v !== null)
  const maxAbsHist = Math.max(...recentHists.map(Math.abs), 0.01)
  const barPct = Math.min((Math.abs(hist) / maxAbsHist) * 50, 50)

  return (
    <div className="space-y-0.5">
      <div className="relative h-1.5 w-full rounded-full bg-muted overflow-hidden">
        {/* Center line */}
        <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
        {/* Histogram bar */}
        <div
          className={`absolute top-0 h-full rounded-full ${positive ? "bg-emerald-500" : "bg-red-500"}`}
          style={{
            left: positive ? "50%" : `${50 - barPct}%`,
            width: `${barPct}%`,
          }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-medium tabular-nums ${positive ? "text-emerald-500" : "text-red-500"}`}>
          MACD {positive ? "+" : ""}{hist.toFixed(2)}
        </span>
        <span className={`text-[10px] ${signal.className}`}>{signal.text}</span>
      </div>
    </div>
  )
}
