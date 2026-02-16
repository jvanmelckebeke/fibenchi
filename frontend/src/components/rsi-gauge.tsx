import { Skeleton } from "@/components/ui/skeleton"

function getMarkerColor(rsi: number): string {
  if (rsi <= 20) return "rgb(239, 68, 68)"       // red-500
  if (rsi <= 30) return "rgb(245, 158, 11)"       // amber-500
  if (rsi <= 40) return "rgb(161, 161, 170)"      // zinc-400
  if (rsi <= 60) return "rgb(161, 161, 170)"      // zinc-400
  if (rsi <= 70) return "rgb(245, 158, 11)"       // amber-500
  if (rsi <= 80) return "rgb(249, 115, 22)"       // orange-500
  return "rgb(239, 68, 68)"                        // red-500
}

function getTextClass(rsi: number): string {
  if (rsi <= 20) return "text-red-400"
  if (rsi <= 30) return "text-amber-400"
  if (rsi <= 70) return "text-muted-foreground"
  if (rsi <= 80) return "text-orange-400"
  return "text-red-400"
}

function getZoneLabel(rsi: number): string {
  if (rsi < 30) return "Oversold"
  if (rsi > 70) return "Overbought"
  return ""
}

export function RsiGauge({ batchRsi }: { symbol: string; batchRsi?: number | null }) {
  if (batchRsi === undefined) {
    return <Skeleton className="h-5 w-full rounded-full" />
  }

  if (batchRsi == null) {
    return (
      <div className="flex items-center justify-center h-5 rounded-full bg-muted text-[10px] text-muted-foreground">
        No RSI
      </div>
    )
  }

  const pct = Math.max(0, Math.min(100, batchRsi))
  const markerColor = getMarkerColor(pct)
  const textClass = getTextClass(pct)
  const label = getZoneLabel(pct)

  return (
    <div className="relative h-5 w-full rounded-full bg-muted overflow-hidden flex items-center px-2">
      {/* Zone backgrounds */}
      <div className="absolute inset-0 flex">
        <div className="w-[30%] bg-amber-500/10" />
        <div className="w-[40%]" />
        <div className="w-[30%] bg-red-500/10" />
      </div>
      {/* Marker */}
      <div
        className="absolute top-0 h-full w-0.5 rounded-full"
        style={{ left: `${pct}%`, backgroundColor: markerColor }}
      />
      {/* Text inside bar */}
      <span className={`relative z-10 text-[10px] font-medium tabular-nums ${textClass}`}>
        RSI {pct.toFixed(0)}
      </span>
      {label && (
        <span className={`relative z-10 text-[10px] ml-auto ${textClass}`}>{label}</span>
      )}
    </div>
  )
}
