import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown, Settings2 } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TagBadge } from "@/components/tag-badge"
import { AssetActionMenu } from "@/components/asset-action-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { ExpandedAssetChart } from "@/components/expanded-asset-chart"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu"
import { ArrowUp, ArrowDown } from "lucide-react"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { GroupSortBy, SortDir } from "@/lib/settings"
import { formatPrice, changeColor } from "@/lib/format"
import {
  getNumericValue,
  extractMacdValues,
  getAllSortableFields,
  getSeriesByField,
  resolveThresholdColor,
  resolveAdxColor,
} from "@/lib/indicator-registry"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useSettings } from "@/lib/settings"

const SORTABLE_FIELDS = getAllSortableFields()

/** Column identifiers for base (non-indicator) toggleable columns. */
const BASE_COLUMN_DEFS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "price", label: "Price" },
  { key: "change_pct", label: "Change %" },
]

/** Check whether a column is visible. Missing key = visible (opt-out model). */
function isColumnVisible(columnSettings: Record<string, boolean>, key: string): boolean {
  return columnSettings[key] !== false
}

interface GroupTableProps {
  assets: Asset[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
  onDelete: (symbol: string) => void
  compactMode: boolean
  onHover?: (symbol: string) => void
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
}

export function GroupTable({ assets, quotes, indicators, onDelete, compactMode, onHover, sortBy, sortDir, onSort }: GroupTableProps) {
  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set())
  const { settings, updateSettings } = useSettings()
  const columnSettings = settings.group_table_columns

  const toggleExpand = (symbol: string) => {
    setExpandedSymbols((prev) => {
      const next = new Set(prev)
      if (next.has(symbol)) next.delete(symbol)
      else next.add(symbol)
      return next
    })
  }

  const toggleColumn = (key: string) => {
    const current = isColumnVisible(columnSettings, key)
    updateSettings({
      group_table_columns: { ...columnSettings, [key]: !current },
    })
  }

  const visibleIndicatorFields = useMemo(
    () => SORTABLE_FIELDS.filter((f) => isColumnVisible(columnSettings, f)),
    [columnSettings],
  )

  // Total visible columns: expand chevron (1) + symbol (1) + toggleable base + toggleable indicators + action menu (1)
  const visibleBaseCount =
    BASE_COLUMN_DEFS.filter((c) => isColumnVisible(columnSettings, c.key)).length
  const totalColSpan = 1 + 1 + visibleBaseCount + visibleIndicatorFields.length + 1

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="w-8" />
            <SortableHeader label="Symbol" sortKey="name" align="left" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            {isColumnVisible(columnSettings, "name") && (
              <th className="text-left text-xs font-medium text-muted-foreground px-3 py-2">Name</th>
            )}
            {isColumnVisible(columnSettings, "price") && (
              <SortableHeader label="Price" sortKey="price" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            )}
            {isColumnVisible(columnSettings, "change_pct") && (
              <SortableHeader label="Change" sortKey="change_pct" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            )}
            {visibleIndicatorFields.map((field) => {
              const series = getSeriesByField(field)
              return (
                <SortableHeader
                  key={field}
                  label={series?.label ?? field}
                  sortKey={field}
                  align="right"
                  sortBy={sortBy}
                  sortDir={sortDir}
                  onSort={onSort}
                />
              )
            })}
            <th className="w-8 text-right pr-1">
              <ColumnVisibilityMenu
                columnSettings={columnSettings}
                onToggle={toggleColumn}
              />
            </th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <TableRow
              key={asset.id}
              asset={asset}
              quote={quotes[asset.symbol]}
              indicator={indicators?.[asset.symbol]}
              expanded={expandedSymbols.has(asset.symbol)}
              onToggle={() => toggleExpand(asset.symbol)}
              onDelete={() => onDelete(asset.symbol)}
              onHover={() => onHover?.(asset.symbol)}
              compactMode={compactMode}
              columnSettings={columnSettings}
              visibleIndicatorFields={visibleIndicatorFields}
              totalColSpan={totalColSpan}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ColumnVisibilityMenu({
  columnSettings,
  onToggle,
}: {
  columnSettings: Record<string, boolean>
  onToggle: (key: string) => void
}) {
  // Build indicator column defs from registry
  const indicatorColumnDefs = useMemo(
    () =>
      SORTABLE_FIELDS.map((field) => {
        const series = getSeriesByField(field)
        return { key: field, label: series?.label ?? field }
      }),
    [],
  )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          aria-label="Toggle column visibility"
        >
          <Settings2 className="h-3.5 w-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>Columns</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {BASE_COLUMN_DEFS.map(({ key, label }) => (
          <DropdownMenuCheckboxItem
            key={key}
            checked={isColumnVisible(columnSettings, key)}
            onCheckedChange={() => onToggle(key)}
            onSelect={(e) => e.preventDefault()}
          >
            {label}
          </DropdownMenuCheckboxItem>
        ))}
        {indicatorColumnDefs.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Indicators</DropdownMenuLabel>
            {indicatorColumnDefs.map(({ key, label }) => (
              <DropdownMenuCheckboxItem
                key={key}
                checked={isColumnVisible(columnSettings, key)}
                onCheckedChange={() => onToggle(key)}
                onSelect={(e) => e.preventDefault()}
              >
                {label}
              </DropdownMenuCheckboxItem>
            ))}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function SortableHeader({
  label,
  sortKey,
  align,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string
  sortKey: GroupSortBy
  align: "left" | "right"
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
}) {
  const active = sortBy === sortKey
  const Icon = active && sortDir === "asc" ? ArrowUp : ArrowDown

  return (
    <th
      className={`${align === "right" ? "text-right" : "text-left"} text-xs font-medium px-3 py-2 ${
        onSort ? "cursor-pointer select-none hover:text-foreground" : ""
      } ${active ? "text-foreground" : "text-muted-foreground"}`}
      onClick={() => onSort?.(sortKey)}
    >
      <span className={`inline-flex items-center gap-0.5 ${align === "right" ? "justify-end" : ""}`}>
        {label}
        {active && <Icon className="h-3 w-3" />}
      </span>
    </th>
  )
}

function TableRow({
  asset,
  quote,
  indicator,
  expanded,
  onToggle,
  onDelete,
  onHover,
  compactMode,
  columnSettings,
  visibleIndicatorFields,
  totalColSpan,
}: {
  asset: Asset
  quote?: Quote
  indicator?: IndicatorSummary
  expanded: boolean
  onToggle: () => void
  onDelete: () => void
  onHover: () => void
  compactMode: boolean
  columnSettings: Record<string, boolean>
  visibleIndicatorFields: string[]
  totalColSpan: number
}) {
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeCls = changeColor(changePct)

  const [priceRef, pctRef] = usePriceFlash(lastPrice)
  const py = compactMode ? "py-1.5" : "py-2.5"

  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/30 cursor-pointer group transition-colors"
        onClick={onToggle}
        onMouseEnter={onHover}
      >
        <td className={`${py} pl-2`}>
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className={`${py} px-3`}>
          <div className="flex items-center gap-2">
            <MarketStatusDot marketState={quote?.market_state} />
            <Link
              to={`/asset/${asset.symbol}`}
              className="font-semibold hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {asset.symbol}
            </Link>
            <Badge variant="secondary" className="text-[10px] px-1 py-0">
              {asset.type}
            </Badge>
          </div>
        </td>
        {isColumnVisible(columnSettings, "name") && (
          <td className={`${py} px-3 text-sm text-muted-foreground max-w-[250px]`}>
            <div className="flex items-center gap-2 truncate">
              <span className="truncate">{asset.name}</span>
              {asset.tags.length > 0 && (
                <span className="flex gap-1 shrink-0">
                  {asset.tags.map((tag) => (
                    <TagBadge key={tag.id} name={tag.name} color={tag.color} />
                  ))}
                </span>
              )}
            </div>
          </td>
        )}
        {isColumnVisible(columnSettings, "price") && (
          <td className={`${py} px-3 text-right tabular-nums`}>
            {lastPrice != null ? (
              <span ref={priceRef} className="font-medium rounded px-1 -mx-1">
                {formatPrice(lastPrice, asset.currency)}
              </span>
            ) : (
              <Skeleton className="h-4 w-14 ml-auto rounded" />
            )}
          </td>
        )}
        {isColumnVisible(columnSettings, "change_pct") && (
          <td className={`${py} px-3 text-right tabular-nums`}>
            {changePct != null ? (
              <span ref={pctRef} className={`font-medium rounded px-1 -mx-1 ${changeCls}`}>
                {changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
            ) : (
              <Skeleton className="h-4 w-12 ml-auto rounded" />
            )}
          </td>
        )}
        {visibleIndicatorFields.map((field) => {
          if (field === "macd") {
            const macdVals = extractMacdValues(indicator?.values)
            const m = macdVals?.macd
            const s = macdVals?.macd_signal
            const h = macdVals?.macd_hist
            const hasValues = m != null || s != null || h != null
            const histColor = h != null ? (h >= 0 ? "text-emerald-400" : "text-red-400") : ""
            const fmt = (v: number | null | undefined) =>
              v != null ? v.toFixed(Math.abs(v) >= 100 ? 0 : 2) : "--"
            return (
              <td key={field} className={`${py} px-3 text-right text-sm tabular-nums`}>
                {hasValues ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="text-muted-foreground">M</span>
                    <span>{fmt(m)}</span>
                    <span className="text-muted-foreground">S</span>
                    <span>{fmt(s)}</span>
                    <span className="text-muted-foreground">H</span>
                    <span className={histColor}>{fmt(h)}</span>
                  </span>
                ) : (
                  <span className="text-muted-foreground">&mdash;</span>
                )}
              </td>
            )
          }
          const val = getNumericValue(indicator?.values, field)
          const series = getSeriesByField(field)
          const colorClass = field === "adx" && val != null && indicator?.values
            ? resolveAdxColor(val, indicator.values)
            : resolveThresholdColor(series?.thresholdColors, val)
          const decimals = val != null && Math.abs(val) >= 100 ? 0 : 2
          return (
            <td key={field} className={`${py} px-3 text-right text-sm tabular-nums`}>
              {val != null ? (
                <span className={colorClass}>{val.toFixed(decimals)}</span>
              ) : (
                <span className="text-muted-foreground">&mdash;</span>
              )}
            </td>
          )
        })}
        <td className={`${py} pr-2`}>
          <AssetActionMenu
            onDelete={onDelete}
            triggerClassName="h-6 w-6 opacity-0 group-hover:opacity-100"
          />
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={totalColSpan} className="bg-muted/20 p-4 border-b border-border">
            <ExpandedAssetChart symbol={asset.symbol} currency={asset.currency} compact />
          </td>
        </tr>
      )}
    </>
  )
}
