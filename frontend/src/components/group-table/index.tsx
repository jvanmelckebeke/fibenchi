import { useCallback, useMemo, useState, type ReactNode } from "react"
import { ChevronsUpDown, ChevronsDownUp, ChevronRight, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { GroupSortBy, SortDir } from "@/lib/settings"
import { getSeriesByField } from "@/lib/indicator-registry"
import { toggleSetItem } from "@/lib/utils"
import { useSettings } from "@/lib/settings"
const noop = () => {}

import { SortableHeader } from "./sortable-header"
import { ColumnVisibilityMenu } from "./column-visibility-menu"
import { TableRow } from "./table-row"
import { SORTABLE_FIELDS, BASE_COLUMN_DEFS, isColumnVisible, useResponsiveHidden } from "./shared"
import { useColumnResize } from "./use-column-resize"


interface GroupTableProps {
  groupId: number
  assets: Asset[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
  onDelete: (symbol: string) => void
  compactMode: boolean
  onHover?: (symbol: string) => void
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
  /**
   * Secondary rows appended below the main rows behind a collapsible in-table
   * footer toggle (e.g. thesis members that live in other groups). Rendered with
   * the same columns — no second header.
   */
  moreAssets?: Asset[]
  /** Label for the "more" footer toggle (e.g. "+2 more in hotlist, Watchlist"). */
  moreLabel?: ReactNode
  /** Controlled open state for the "more" footer. Falls back to internal state. */
  moreOpen?: boolean
  /** Controlled toggle handler for the "more" footer. */
  onToggleMore?: () => void
  /**
   * Per-symbol left-border accent colour (thesis colour) for the "inline" thesis
   * grouping mode. Rows without an entry render no accent.
   */
  accentColors?: Record<string, string>
  /** Per-symbol tooltip for the accent bar (the thesis name[s]). */
  accentTitles?: Record<string, string>
  /** Per-symbol Lucide icon name (the thesis icon) revealed when hovering the accent bar. */
  accentIcons?: Record<string, string>
}

export function GroupTable({ groupId, assets, quotes, indicators, onDelete, compactMode, onHover, sortBy, sortDir, onSort, moreAssets, moreLabel, moreOpen, onToggleMore, accentColors, accentTitles, accentIcons }: GroupTableProps) {
  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set())
  const [internalMoreOpen, setInternalMoreOpen] = useState(false)
  const moreOpenState = moreOpen ?? internalMoreOpen
  const toggleMore = onToggleMore ?? (() => setInternalMoreOpen((o) => !o))
  const { settings, updateSettings } = useSettings()
  const columnSettings = settings.group_table_columns
  const responsiveHidden = useResponsiveHidden()
  const { getColumnStyle, startResize, resetWidth } = useColumnResize()

  const toggleExpand = useCallback((symbol: string) => {
    setExpandedSymbols((prev) => toggleSetItem(prev, symbol))
  }, [])

  const toggleColumn = (key: string) => {
    const current = isColumnVisible(columnSettings, key)
    updateSettings({
      group_table_columns: { ...columnSettings, [key]: !current },
    })
  }

  const allExpanded = assets.length > 0 && assets.every((a) => expandedSymbols.has(a.symbol))

  const toggleExpandAll = () => {
    if (allExpanded) {
      setExpandedSymbols(new Set())
    } else {
      setExpandedSymbols(new Set(assets.map((a) => a.symbol)))
    }
  }

  const visibleIndicatorFields = useMemo(
    () => SORTABLE_FIELDS.filter((f) => isColumnVisible(columnSettings, f) && !responsiveHidden.has(f)),
    [columnSettings, responsiveHidden],
  )

  // Total visible columns: expand chevron (1) + symbol (1) + toggleable base + toggleable indicators
  const visibleBaseCount =
    BASE_COLUMN_DEFS.filter((c) => isColumnVisible(columnSettings, c.key)).length
  const totalColSpan = 1 + 1 + visibleBaseCount + visibleIndicatorFields.length

  const hasMore = !!moreAssets && moreAssets.length > 0

  const renderRow = (asset: Asset, keyPrefix = "") => (
    <TableRow
      key={`${keyPrefix}${asset.id}`}
      groupId={groupId}
      asset={asset}
      quote={quotes[asset.symbol]}
      indicator={indicators?.[asset.symbol]}
      expanded={expandedSymbols.has(asset.symbol)}
      onToggle={toggleExpand}
      onDelete={onDelete}
      onHover={onHover ?? noop}
      compactMode={compactMode}
      columnSettings={columnSettings}
      visibleIndicatorFields={visibleIndicatorFields}
      totalColSpan={totalColSpan}
      accent={accentColors?.[asset.symbol]}
      accentTitle={accentTitles?.[asset.symbol]}
      accentIcon={accentIcons?.[asset.symbol]}
    />
  )

  return (
    <div className="rounded-md border border-border overflow-x-auto">
      <div className="flex items-center justify-end gap-0.5 px-1 py-0.5">
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 px-1.5 text-xs text-muted-foreground"
          onClick={toggleExpandAll}
        >
          {allExpanded ? (
            <ChevronsDownUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronsUpDown className="h-3.5 w-3.5" />
          )}
          {allExpanded ? "Collapse" : "Expand"}
        </Button>
        <ColumnVisibilityMenu
          columnSettings={columnSettings}
          onToggle={toggleColumn}
          responsiveHidden={responsiveHidden}
        />
      </div>
      <table className="w-full table-fixed">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="w-8" />
            <SortableHeader
              label="Symbol" sortKey="name" align="left"
              sortBy={sortBy} sortDir={sortDir} onSort={onSort}
              style={getColumnStyle("symbol")}
              onResizeStart={(e) => startResize("symbol", e)}
              onResizeReset={(e) => resetWidth("symbol", e)}
            />
            {isColumnVisible(columnSettings, "name") && (
              <th
                className="relative text-left text-xs font-medium text-muted-foreground px-3 py-2"
                style={getColumnStyle("name")}
              >
                Name
                <button
                  type="button"
                  aria-label="Resize Name column"
                  tabIndex={-1}
                  className="absolute right-0 top-1 bottom-1 w-0.5 cursor-col-resize bg-border/50 hover:bg-primary/40 transition-colors border-0 p-0"
                  onPointerDown={(e) => startResize("name", e)}
                  onDoubleClick={(e) => resetWidth("name", e)}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
            )}
            {isColumnVisible(columnSettings, "price") && (
              <SortableHeader
                label="Price" sortKey="price" align="right"
                sortBy={sortBy} sortDir={sortDir} onSort={onSort}
                style={getColumnStyle("price")}
                onResizeStart={(e) => startResize("price", e)}
                onResizeReset={(e) => resetWidth("price", e)}
              />
            )}
            {isColumnVisible(columnSettings, "change_pct") && (
              <SortableHeader
                label="Change" sortKey="change_pct" align="right"
                sortBy={sortBy} sortDir={sortDir} onSort={onSort}
                style={getColumnStyle("change_pct")}
                onResizeStart={(e) => startResize("change_pct", e)}
                onResizeReset={(e) => resetWidth("change_pct", e)}
              />
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
                  style={getColumnStyle(field)}
                  onResizeStart={(e) => startResize(field, e)}
                  onResizeReset={(e) => resetWidth(field, e)}
                />
              )
            })}
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => renderRow(asset))}
          {hasMore && (
            <>
              <tr className="border-b border-border bg-muted/20">
                <td colSpan={totalColSpan} className="p-0">
                  <button
                    type="button"
                    onClick={toggleMore}
                    className="flex w-full items-center gap-1 px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
                    aria-expanded={moreOpenState}
                  >
                    {moreOpenState ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
                    {moreLabel}
                  </button>
                </td>
              </tr>
              {moreOpenState && moreAssets!.map((asset) => renderRow(asset, "more-"))}
            </>
          )}
        </tbody>
      </table>
    </div>
  )
}
