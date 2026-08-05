import type { ReactNode } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { OrphansCard } from "@/components/stats/orphans-card"
import { useDataHealth, useSystemStats } from "@/lib/queries"
import type { Stats } from "@/lib/types"

function formatEta(seconds: number): string {
  if (seconds < 60) return "under a minute"
  const minutes = Math.round(seconds / 60)
  if (minutes < 90) return `~${minutes} min`
  return `~${Math.round(minutes / 60)} h`
}

const num = (n: number) => n.toLocaleString("en-US")

const MIX_SEGMENTS = [
  { key: "stocks", label: "Stocks", color: "#3b82f6" },
  { key: "etfs", label: "ETFs", color: "#8b5cf6" },
  { key: "indexes", label: "Indexes", color: "#f59e0b" },
  { key: "crypto", label: "Crypto", color: "#10b981" },
  { key: "futures", label: "Futures", color: "#ef4444" },
  { key: "fx", label: "FX", color: "#64748b" },
] as const satisfies readonly { key: keyof Stats; label: string; color: string }[]

/** Asset-mix breakdown: stacked proportion bar + per-kind legend counts. */
function AssetMixCard({ stats }: { stats: Stats }) {
  const segments = MIX_SEGMENTS
    .map((s) => ({ ...s, count: stats[s.key] }))
    .filter((s) => s.count > 0)
  const total = segments.reduce((acc, s) => acc + s.count, 0)

  return (
    <Card className="col-span-2">
      <CardContent className="pt-6 space-y-3">
        <div className="flex items-baseline justify-between">
          <p className="text-sm text-muted-foreground">Tracked tickers</p>
          <p className="text-2xl font-bold tabular-nums">{num(stats.assets_tracked)}</p>
        </div>

        {total > 0 && (
          <>
            <div className="flex h-3 w-full overflow-hidden rounded-full" role="img"
                 aria-label={segments.map((s) => `${s.count} ${s.label}`).join(", ")}>
              {segments.map((s) => (
                <div
                  key={s.key}
                  style={{ width: `${(s.count / total) * 100}%`, backgroundColor: s.color }}
                  title={`${s.label}: ${s.count}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {segments.map((s) => (
                <span key={s.key} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="tabular-nums font-medium">{num(s.count)}</span>
                  <span className="text-muted-foreground">{s.label}</span>
                </span>
              ))}
            </div>
          </>
        )}

        {(stats.assets_thesis_or_etf_only > 0 || stats.assets_orphaned > 0) && (
          <p className="text-xs text-muted-foreground">
            {[
              stats.assets_thesis_or_etf_only > 0 &&
                `${num(stats.assets_thesis_or_etf_only)} not in a group but tracked by a thesis or pseudo-ETF`,
              stats.assets_orphaned > 0 &&
                `${num(stats.assets_orphaned)} orphaned (removed from groups; no thesis or pseudo-ETF uses ${stats.assets_orphaned === 1 ? "it" : "them"})`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function StatTile({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold tabular-nums">{value}</p>
        {detail && <p className="text-xs text-muted-foreground mt-1">{detail}</p>}
      </CardContent>
    </Card>
  )
}

/**
 * Session-bar completeness donut + self-heal status. The percentage is
 * stored-vs-scheduled session bars over the heal's scan window; symbols
 * listed under it show a blank σ-Move until the background heal repairs
 * them.
 */
function DataQualityCard() {
  const { data, isPending, isError } = useDataHealth()

  if (isPending || isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Data Quality</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {isPending ? "Checking stored price history…" : "Data-health status unavailable."}
        </CardContent>
      </Card>
    )
  }

  const expected = data.expected_session_bars
  const missing = data.total_missing_sessions
  const pct = expected > 0 ? ((expected - missing) / expected) * 100 : 100
  // Never show a rounded "100%" while bars are missing.
  const pctLabel = missing > 0 ? Math.min(pct, 99.9).toFixed(1) : "100"
  const healthy = missing === 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Quality</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div
          className="relative h-36 w-36 shrink-0 rounded-full"
          style={{
            background: `conic-gradient(${healthy ? "#10b981" : "#f97316"} ${pct}%, ${
              healthy ? "#10b981" : "rgba(249, 115, 22, 0.2)"
            } 0)`,
          }}
          role="img"
          aria-label={`${pctLabel}% of expected session bars present`}
        >
          <div className="absolute inset-3 flex flex-col items-center justify-center rounded-full bg-card">
            <span className="text-2xl font-bold tabular-nums">{pctLabel}%</span>
            <span className="text-xs text-muted-foreground">complete</span>
          </div>
        </div>

        <div className="space-y-2 text-sm">
          {healthy ? (
            <p>
              All {num(expected)} expected session bars of the last {data.scan_window_days} days
              are present. Nothing to heal.
            </p>
          ) : (
            <>
              <p>
                {num(expected - missing)} of {num(expected)} expected session bars present —{" "}
                <span className="font-medium">
                  {missing} missing across {data.hole_symbols.length}{" "}
                  {data.hole_symbols.length === 1 ? "symbol" : "symbols"}
                </span>
                . Their σ-Move shows "—" until repaired.
              </p>
              <p className="text-muted-foreground">
                Self-heals automatically: next scan {formatEta(data.next_scan_in_seconds)}, up to{" "}
                {data.heals_per_scan} symbols per scan, most recent gaps first.
              </p>
              <details>
                <summary className="cursor-pointer text-muted-foreground">Affected symbols</summary>
                <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
                  {data.hole_symbols.map((h) => (
                    <li key={h.symbol} className="flex justify-between gap-4">
                      <span className="font-medium">{h.symbol}</span>
                      <span className="text-muted-foreground truncate">
                        {h.missing_sessions.join(", ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export function StatsPage() {
  const { data: stats } = useSystemStats()

  const years = stats && stats.collected_days > 0 ? stats.collected_days / 365 : 0

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Stats</h1>

      <DataQualityCard />

      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          <AssetMixCard stats={stats} />
          <StatTile
            label="Daily price bars"
            value={num(stats.price_bars)}
            detail={
              stats.earliest_bar
                ? `since ${stats.earliest_bar} · ${years >= 1 ? `${years.toFixed(1)} years` : `${stats.collected_days} days`} of history`
                : undefined
            }
          />
          <StatTile
            label="Intraday bars"
            value={num(stats.intraday_bars)}
            detail="1-minute bars, rolling window"
          />
          <StatTile
            label="Symbol directory"
            value={num(stats.symbol_directory_entries)}
            detail="searchable symbols"
          />
          <StatTile label="Groups" value={num(stats.groups)} />
          <StatTile label="Pseudo-ETFs" value={num(stats.pseudo_etfs)} />
          <StatTile label="Theses" value={num(stats.theses)} />
          <StatTile
            label="Tags & annotations"
            value={`${num(stats.tags)} / ${num(stats.annotations)}`}
            detail="tags / chart annotations"
          />
        </div>
      )}

      <OrphansCard />
    </div>
  )
}
