import { useMemo } from "react"
import { useEarnings } from "@/lib/queries"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

const DIAL_SIZE = 96
const STROKE = 6
const RADIUS = (DIAL_SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const MAX_DAYS = 90
const POST_EARNINGS_DAYS = 14

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00")
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - now.getTime()) / 86_400_000)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function getColor(days: number): { stroke: string; text: string } {
  if (days <= 14) return { stroke: "stroke-red-500", text: "text-red-500" }
  if (days <= 30) return { stroke: "stroke-amber-500", text: "text-amber-500" }
  return { stroke: "stroke-emerald-500", text: "text-emerald-500" }
}

export function EarningsCountdown({ symbol }: { symbol: string }) {
  const { data, isLoading } = useEarnings(symbol)

  const state = useMemo(() => {
    if (!data?.earnings_date) return null

    // Check if we're in the post-earnings window via last_reported_date
    if (data.last_reported_date) {
      const daysSinceReport = -daysUntil(data.last_reported_date)
      if (daysSinceReport >= 0 && daysSinceReport <= POST_EARNINGS_DAYS) {
        return { mode: "post-earnings" as const, daysSince: daysSinceReport, reportedDate: data.last_reported_date }
      }
    }

    const days = daysUntil(data.earnings_date)
    if (days < 0) return null

    return { mode: "countdown" as const, days, date: data.earnings_date, isEstimate: data.is_estimate }
  }, [data])

  if (isLoading) {
    return (
      <div className="flex items-center gap-4">
        <Skeleton className="h-24 w-24 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
    )
  }

  if (!state) return null

  if (state.mode === "post-earnings") {
    const { daysSince, reportedDate } = state
    // Drain from full to empty over POST_EARNINGS_DAYS
    const remaining = 1 - daysSince / POST_EARNINGS_DAYS
    const postOffset = CIRCUMFERENCE * (1 - remaining)

    return (
      <div className="flex items-center gap-4">
        <div className="relative" style={{ width: DIAL_SIZE, height: DIAL_SIZE }}>
          <svg width={DIAL_SIZE} height={DIAL_SIZE} className="-rotate-90">
            <circle
              cx={DIAL_SIZE / 2}
              cy={DIAL_SIZE / 2}
              r={RADIUS}
              fill="none"
              className="stroke-amber-500/15"
              strokeWidth={STROKE}
            />
            <circle
              cx={DIAL_SIZE / 2}
              cy={DIAL_SIZE / 2}
              r={RADIUS}
              fill="none"
              className="stroke-amber-500 transition-all duration-500"
              strokeWidth={STROKE}
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={postOffset}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xs font-bold text-amber-500 animate-pulse">POST</span>
            <span className="text-[10px] text-amber-500/70">{daysSince}d ago</span>
          </div>
        </div>
        <div className="space-y-1">
          <p className="text-sm font-semibold text-amber-500">Post-Earnings</p>
          <p className="text-xs text-muted-foreground">
            Reported {formatDate(reportedDate)} — price action may be noisy
          </p>
        </div>
      </div>
    )
  }

  // Countdown mode
  const { days, date, isEstimate } = state
  const progress = Math.min(1, Math.max(0, 1 - days / MAX_DAYS))
  const offset = CIRCUMFERENCE * (1 - progress)
  const color = getColor(days)

  return (
    <div className="flex items-center gap-4">
      <div className="relative" style={{ width: DIAL_SIZE, height: DIAL_SIZE }}>
        <svg width={DIAL_SIZE} height={DIAL_SIZE} className="-rotate-90">
          <circle
            cx={DIAL_SIZE / 2}
            cy={DIAL_SIZE / 2}
            r={RADIUS}
            fill="none"
            className="stroke-muted"
            strokeWidth={STROKE}
          />
          <circle
            cx={DIAL_SIZE / 2}
            cy={DIAL_SIZE / 2}
            r={RADIUS}
            fill="none"
            className={cn(color.stroke, "transition-all duration-500")}
            strokeWidth={STROKE}
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-2xl font-bold tabular-nums", color.text)}>{days}</span>
          <span className="text-[10px] text-muted-foreground">days</span>
        </div>
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-muted-foreground">Earnings Countdown</p>
        <p className="text-sm">{formatDate(date)}</p>
        {isEstimate && <Badge variant="outline" className="text-[10px]">Estimated</Badge>}
      </div>
    </div>
  )
}
