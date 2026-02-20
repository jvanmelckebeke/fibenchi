import { useState } from "react"
import { toggleSetItem } from "@/lib/utils"
import { HoldingRow } from "./holding-row"
import { SUMMARY_DESCRIPTORS } from "./types"
import type { HoldingsGridRow, IndicatorData } from "./types"

export type { IndicatorData, HoldingsGridRow } from "./types"

interface HoldingsGridProps {
  rows: HoldingsGridRow[]
  indicatorMap: ReadonlyMap<string, IndicatorData>
  indicatorsLoading: boolean
  onRemove?: (key: string | number) => void
  linkTarget?: "_blank"
}

export function HoldingsGrid({ rows, indicatorMap, indicatorsLoading, onRemove, linkTarget }: HoldingsGridProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string | number>>(new Set())
  const hasRemove = !!onRemove

  const toggleExpand = (key: string | number) => {
    setExpandedKeys((prev) => toggleSetItem(prev, key))
  }

  // base columns: chevron + symbol + name + % + price + chg% + indicator summary columns + optional remove
  const totalColSpan = 1 + 1 + 1 + 1 + 1 + 1 + SUMMARY_DESCRIPTORS.length + (hasRemove ? 1 : 0)

  return (
    <div className="overflow-x-auto">
      <div className={hasRemove ? "min-w-[750px]" : "min-w-[700px]"}>
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="w-6" />
              <th className="text-left text-xs font-medium text-muted-foreground px-2 py-1">Symbol</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-2 py-1">Name</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">%</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">Price</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">Chg%</th>
              {SUMMARY_DESCRIPTORS.map((desc) => (
                <th key={desc.id} className="text-right text-xs font-medium text-muted-foreground px-2 py-1">
                  {desc.holdingSummary.label}
                </th>
              ))}
              {hasRemove && <th className="w-8" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <HoldingRow
                key={row.key}
                row={row}
                indicator={indicatorMap.get(row.symbol)}
                indicatorsLoading={indicatorsLoading}
                expanded={expandedKeys.has(row.key)}
                onToggle={() => toggleExpand(row.key)}
                onRemove={onRemove ? () => onRemove(row.key) : undefined}
                linkTarget={linkTarget}
                totalColSpan={totalColSpan}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
