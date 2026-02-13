import { Skeleton } from "@/components/ui/skeleton"
import { useIndicators } from "@/lib/queries"

// Gradual color: center (50) is neutral, extremes get more intense
function getMarkerColor(rsi: number): string {
  if (rsi <= 20) return "rgb(239, 68, 68)"       // red-500
  if (rsi <= 30) return "rgb(245, 158, 11)"       // amber-500
  if (rsi <= 40) return "rgb(161, 161, 170)"      // zinc-400
  if (rsi <= 60) return "rgb(161, 161, 170)"      // zinc-400
  if (rsi <= 70) return "rgb(245, 158, 11)"        // amber-500
  if (rsi <= 80) return "rgb(249, 115, 22)"        // orange-500
  return "rgb(239, 68, 68)"                        // red-500
}

function getTextClass(rsi: number): string {
  if (rsi <= 20) return "text-red-500"
  if (rsi <= 30) return "text-amber-500"
  if (rsi <= 70) return "text-muted-foreground"
  if (rsi <= 80) return "text-orange-500"
  return "text-red-500"
}

function getZoneLabel(rsi: number): string {
  if (rsi < 30) return "Oversold"
  if (rsi > 70) return "Overbought"
  return ""
}

export function RsiGauge({ symbol }: { symbol: string }) {
  const { data: indicators, isLoading } = useIndicators(symbol)

  const latestRsi = indicators
    ?.slice()
    .reverse()
    .find((i) => i.rsi !== null)?.rsi

  if (isLoading) {
    return (
      <div className="mt-2 space-y-1">
        <Skeleton className="h-1.5 w-full rounded-full" />
        <Skeleton className="h-3 w-14 rounded" />
      </div>
    )
  }

  if (latestRsi == null) {
    return (
      <div className="flex items-center justify-center h-5 text-[10px] text-muted-foreground">
        No RSI
      </div>
    )
  }

  const pct = Math.max(0, Math.min(100, latestRsi))
  const markerColor = getMarkerColor(pct)
  const textClass = getTextClass(pct)
  const label = getZoneLabel(pct)

  return (
    <div className="mt-2 space-y-0.5">
      <div className="relative h-1.5 w-full rounded-full bg-muted overflow-hidden">
        {/* Zone backgrounds */}
        <div className="absolute inset-0 flex">
          <div className="w-[30%] bg-amber-500/15" />
          <div className="w-[40%]" />
          <div className="w-[30%] bg-red-500/15" />
        </div>
        {/* Marker */}
        <div
          className="absolute top-0 h-full w-1 rounded-full"
          style={{ left: `calc(${pct}% - 2px)`, backgroundColor: markerColor }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-medium tabular-nums ${textClass}`}>
          RSI {pct.toFixed(0)}
        </span>
        {label && (
          <span className={`text-[10px] ${textClass}`}>{label}</span>
        )}
      </div>
    </div>
  )
}
