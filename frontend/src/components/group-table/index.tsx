import { useMemo, useState } from "react"
import { ChevronsUpDown, ChevronsDownUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { GroupSortBy, SortDir } from "@/lib/settings"
import { getSeriesByField } from "@/lib/indicator-registry"
import { toggleSetItem } from "@/lib/utils"
import { useSettings } from "@/lib/settings"
import { SortableHeader } from "./sortable-header"
import { ColumnVisibilityMenu } from "./column-visibility-menu"
import { TableRow } from "./table-row"
import { SORTABLE_FIELDS, BASE_COLUMN_DEFS, isColumnVisible } from "./shared"

export { SORTABLE_FIELDS, BASE_COLUMN_DEFS, isColumnVisible }

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
    setExpandedSymbols((prev) => toggleSetItem(prev, symbol))
  }

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
              <div className="flex items-center justify-end gap-0.5">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  aria-label={allExpanded ? "Collapse all rows" : "Expand all rows"}
                  onClick={toggleExpandAll}
                >
                  {allExpanded ? (
                    <ChevronsDownUp className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronsUpDown className="h-3.5 w-3.5" />
                  )}
                </Button>
                <ColumnVisibilityMenu
                  columnSettings={columnSettings}
                  onToggle={toggleColumn}
                />
              </div>
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
