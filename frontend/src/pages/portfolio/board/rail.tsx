// The rail: three summary cards, each owning its own window where it needs
// one (design principle 3 — a control sits next to what it scopes; the index
// period and the movers window are independent and must not couple).

import { useState } from "react"
import { Link } from "react-router-dom"
import { SparklineChart } from "@/components/chart/sparkline"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { usePortfolioIndex } from "@/lib/queries"
import { changeColor, formatChangePct } from "@/lib/format"
import { PCT_WINDOWS, pctWindowDef, type PctWindow } from "./color-scale"
import type { Tile } from "./use-board-data"

const INDEX_PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

function RailCard({
  title,
  control,
  children,
}: {
  title: string
  control?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="rounded-md border border-border bg-card p-4 2xl:p-5">
      <header className="mb-2.5 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        {control}
      </header>
      {children}
    </section>
  )
}

export function IndexCard() {
  const [period, setPeriod] = useState<string>("1y")
  const { data, isLoading } = usePortfolioIndex(period)

  return (
    <RailCard
      title="Portfolio index"
      control={
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger size="sm" className="h-6 w-[70px] px-2 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {INDEX_PERIODS.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      }
    >
      {isLoading || !data ? (
        <div className="h-[96px] animate-pulse rounded bg-muted/40" />
      ) : !data.dates.length ? (
        <p className="text-xs text-muted-foreground">No data yet.</p>
      ) : (
        <div className="space-y-1.5">
          <div className="text-3xl font-light tabular-nums 2xl:text-4xl">
            {data.current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={`text-sm font-medium tabular-nums 2xl:text-[15px] ${changeColor(data.change)}`}>
            {data.change >= 0 ? "+" : ""}
            {data.change.toFixed(2)} · {formatChangePct(data.change_pct).text}
          </div>
          <SparklineChart
            batchData={data.dates.map((d, i) => ({ date: d, close: data.values[i] }))}
          />
        </div>
      )}
    </RailCard>
  )
}

function MoverRow({ tile, pct, maxAbs }: { tile: Tile; pct: number; maxAbs: number }) {
  const width = maxAbs > 0 ? Math.min(100, (Math.abs(pct) / maxAbs) * 100) : 0
  return (
    <Link
      to={`/asset/${tile.symbol}`}
      className="relative flex items-center justify-between gap-2 rounded px-2 py-1 text-[13px] hover:bg-muted/40 2xl:py-1.5 2xl:text-sm"
    >
      <span
        aria-hidden
        className={`absolute inset-y-0.5 left-0 rounded-sm ${pct >= 0 ? "bg-emerald-500/10" : "bg-red-500/10"}`}
        style={{ width: `${width}%` }}
      />
      <span className="relative font-mono">{tile.symbol}</span>
      <span className={`relative tabular-nums ${changeColor(pct)}`}>{formatChangePct(pct).text}</span>
    </Link>
  )
}

export function MoversCard({ tiles }: { tiles: Tile[] }) {
  const [window, setWindow] = useState<PctWindow>("1wk")
  const ranked = tiles
    .map((t) => ({ tile: t, pct: t.windowPct[window] }))
    .filter((r): r is { tile: Tile; pct: number } => r.pct != null)
    .sort((a, b) => b.pct - a.pct)
  const up = ranked.filter((r) => r.pct > 0).slice(0, 5)
  const down = ranked.filter((r) => r.pct < 0).slice(-5).reverse()
  const maxAbs = Math.max(...ranked.map((r) => Math.abs(r.pct)), 0)
  const missing = tiles.length - ranked.length

  return (
    <RailCard
      title="Movers"
      control={
        <SegmentedControl<PctWindow>
          options={PCT_WINDOWS.map((w) => ({ value: w.value, label: w.value, title: `over ${w.label}` }))}
          value={window}
          onChange={setWindow}
        />
      }
    >
      {ranked.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No {pctWindowDef(window).label} readings yet.
        </p>
      ) : (
        <div className="space-y-0.5">
          {up.map((r) => (
            <MoverRow key={r.tile.symbol} tile={r.tile} pct={r.pct} maxAbs={maxAbs} />
          ))}
          {up.length > 0 && down.length > 0 && <div className="my-1 border-t border-border/60" />}
          {down.map((r) => (
            <MoverRow key={r.tile.symbol} tile={r.tile} pct={r.pct} maxAbs={maxAbs} />
          ))}
          {/* Never average (or rank) over a hole without saying so. */}
          {missing > 0 && (
            <p className="pt-1 text-xs text-muted-foreground">
              {missing} without a {pctWindowDef(window).label} series
            </p>
          )}
        </div>
      )}
    </RailCard>
  )
}

export function MostUnusualCard({ tiles }: { tiles: Tile[] }) {
  const scored = tiles
    .filter((t): t is Tile & { sigma: number } => t.sigma != null)
    .sort((a, b) => Math.abs(b.sigma) - Math.abs(a.sigma))
    .slice(0, 6)
  const unscored = tiles.filter((t) => t.sigma == null).length

  return (
    <RailCard title="Most unusual" control={<span className="text-xs text-muted-foreground">today</span>}>
      {scored.length === 0 ? (
        <p className="text-xs text-muted-foreground">No readings.</p>
      ) : (
        <div className="space-y-0.5">
          {scored.map((t) => (
            <Link
              key={t.symbol}
              to={`/asset/${t.symbol}`}
              className="flex items-center justify-between gap-2 rounded px-2 py-1 text-[13px] hover:bg-muted/40 2xl:py-1.5 2xl:text-sm"
            >
              <span className="font-mono">{t.symbol}</span>
              <span className={`tabular-nums ${changeColor(t.sigma)}`}>
                {t.sigma > 0 ? "+" : ""}
                {t.sigma.toFixed(1)}σ
              </span>
            </Link>
          ))}
        </div>
      )}
      {unscored > 0 && (
        <p className="mt-2 border-t border-border/60 pt-2 text-xs text-muted-foreground">
          {unscored} asset{unscored === 1 ? "" : "s"} without a σ today — still listed in Movers.
        </p>
      )}
    </RailCard>
  )
}
