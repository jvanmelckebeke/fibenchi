import { useIndicators } from "@/lib/queries"

function getZoneColor(rsi: number): { bar: string; text: string } {
  if (rsi < 30) return { bar: "bg-emerald-500", text: "text-emerald-500" }
  if (rsi > 70) return { bar: "bg-red-500", text: "text-red-500" }
  return { bar: "bg-zinc-400 dark:bg-zinc-500", text: "text-muted-foreground" }
}

function getZoneLabel(rsi: number): string {
  if (rsi < 30) return "Oversold"
  if (rsi > 70) return "Overbought"
  return ""
}

export function RsiGauge({ symbol }: { symbol: string }) {
  const { data: indicators } = useIndicators(symbol)

  const latestRsi = indicators
    ?.slice()
    .reverse()
    .find((i) => i.rsi !== null)?.rsi

  if (latestRsi == null) {
    return (
      <div className="flex items-center justify-center h-5 text-[10px] text-muted-foreground">
        No RSI
      </div>
    )
  }

  const pct = Math.max(0, Math.min(100, latestRsi))
  const zone = getZoneColor(pct)
  const label = getZoneLabel(pct)

  return (
    <div className="space-y-0.5">
      <div className="relative h-1.5 w-full rounded-full bg-muted overflow-hidden">
        {/* Zone background gradient */}
        <div className="absolute inset-0 flex">
          <div className="w-[30%] bg-emerald-500/15" />
          <div className="w-[40%]" />
          <div className="w-[30%] bg-red-500/15" />
        </div>
        {/* Marker */}
        <div
          className={`absolute top-0 h-full w-1 rounded-full ${zone.bar}`}
          style={{ left: `calc(${pct}% - 2px)` }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-medium tabular-nums ${zone.text}`}>
          RSI {pct.toFixed(0)}
        </span>
        {label && (
          <span className={`text-[10px] ${zone.text}`}>{label}</span>
        )}
      </div>
    </div>
  )
}
