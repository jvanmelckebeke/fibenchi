import { Skeleton } from "@/components/ui/skeleton"
import type { IndicatorSummary } from "@/lib/api"
import { useSettings } from "@/lib/settings"

type MacdProps = { macd: number; sig: number; hist: number }

function ClassicMacd({ macd, sig, hist }: MacdProps) {
  const histPositive = hist >= 0
  const bullish = macd > sig
  const barPct = 25

  const histColor = histPositive ? "bg-emerald-500/30" : "bg-red-500/30"
  const macdTextColor = bullish ? "text-emerald-400" : "text-red-400"
  const histTextColor = histPositive ? "text-emerald-400" : "text-red-400"

  return (
    <div className="relative h-5 w-full rounded-full bg-muted overflow-hidden flex items-center px-2">
      <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
      <div
        className={`absolute top-0 h-full ${histColor}`}
        style={{
          left: histPositive ? "50%" : `${50 - barPct}%`,
          width: `${barPct}%`,
        }}
      />
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

function DivergenceMacd({ macd, sig, hist }: MacdProps) {
  const histPositive = hist >= 0
  const bullish = macd > sig
  const barPct = 25

  const barColor = histPositive ? "bg-emerald-500/30" : "bg-red-500/30"
  const trendColor = bullish ? "text-emerald-400" : "text-red-400"
  const dotFill = bullish ? "bg-emerald-400" : "bg-red-400"
  const histTextColor = histPositive ? "text-emerald-400" : "text-red-400"

  const strength = Math.abs(hist)
  const dots = strength > 0.5 ? 3 : strength > 0.15 ? 2 : 1

  return (
    <div className="relative h-5 w-full rounded-full bg-muted overflow-hidden flex items-center px-2">
      <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
      <div
        className={`absolute top-0 h-full ${barColor}`}
        style={{
          left: histPositive ? "50%" : `${50 - barPct}%`,
          width: `${barPct}%`,
        }}
      />
      <span className={`relative z-10 text-[10px] font-medium tabular-nums ${trendColor}`}>
        {bullish ? "\u25B2" : "\u25BC"} {macd.toFixed(2)}
      </span>
      <span className="relative z-10 flex items-center gap-0.5 ml-1.5">
        {Array.from({ length: dots }).map((_, i) => (
          <span key={i} className={`inline-block h-1 w-1 rounded-full ${dotFill}`} />
        ))}
        {Array.from({ length: 3 - dots }).map((_, i) => (
          <span key={i} className="inline-block h-1 w-1 rounded-full bg-muted-foreground/20" />
        ))}
      </span>
      <span className={`relative z-10 text-[10px] font-medium tabular-nums ml-auto ${histTextColor}`}>
        {histPositive ? "+" : ""}{hist.toFixed(2)}
      </span>
    </div>
  )
}

export function MacdIndicator({
  batchMacd,
}: {
  symbol: string
  batchMacd?: Pick<IndicatorSummary, "macd" | "macd_signal" | "macd_hist"> | null
}) {
  const { settings } = useSettings()

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

  const props: MacdProps = {
    macd: batchMacd.macd,
    sig: batchMacd.macd_signal,
    hist: batchMacd.macd_hist,
  }

  return settings.watchlist_macd_style === "classic"
    ? <ClassicMacd {...props} />
    : <DivergenceMacd {...props} />
}
