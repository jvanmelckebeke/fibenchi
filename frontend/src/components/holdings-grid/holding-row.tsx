import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ExpandedAssetChart } from "@/components/expanded-asset-chart"
import { formatPrice, formatChangePct } from "@/lib/format"
import { HoldingSummaryCell } from "./holding-summary-cell"
import { SUMMARY_DESCRIPTORS } from "./types"
import type { HoldingsGridRow, IndicatorData } from "./types"

export function HoldingRow({
  row,
  indicator,
  indicatorsLoading,
  expanded,
  onToggle,
  onRemove,
  linkTarget,
  totalColSpan,
}: {
  row: HoldingsGridRow
  indicator: IndicatorData | undefined
  indicatorsLoading: boolean
  expanded: boolean
  onToggle: () => void
  onRemove?: () => void
  linkTarget?: "_blank"
  totalColSpan: number
}) {
  const chg = formatChangePct(indicator?.change_pct ?? null)

  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/30 cursor-pointer group/row transition-colors"
        onClick={onToggle}
      >
        <td className="py-1 pl-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="py-1 px-2">
          <Link
            to={`/asset/${row.symbol}`}
            {...(linkTarget === "_blank" ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            className="font-mono text-xs text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {row.symbol}
          </Link>
        </td>
        <td className="py-1 px-2 text-muted-foreground truncate text-xs max-w-[200px]">
          {row.name}
        </td>
        <td className="py-1 px-2 text-right text-xs">
          {row.percent != null ? `${row.percent.toFixed(1)}%` : "\u2014"}
        </td>
        {indicatorsLoading ? (
          <td
            colSpan={2 + SUMMARY_DESCRIPTORS.length}
            className="py-1 px-2 text-right text-xs text-muted-foreground animate-pulse"
          >
            Loading...
          </td>
        ) : (
          <>
            <td className="py-1 px-2 text-right text-xs">
              {indicator?.close != null ? formatPrice(indicator.close, indicator.currency, 0) : "\u2014"}
            </td>
            <td className={`py-1 px-2 text-right text-xs ${chg.className}`}>
              {chg.text ?? "\u2014"}
            </td>
            {SUMMARY_DESCRIPTORS.map((desc) => {
              const hs = desc.holdingSummary
              return (
                <td key={desc.id} className="py-1 px-2 text-right">
                  <HoldingSummaryCell
                    format={hs.format}
                    field={hs.field}
                    colorMap={hs.colorMap}
                    values={indicator?.values}
                    close={indicator?.close ?? null}
                  />
                </td>
              )
            })}
          </>
        )}
        {onRemove && (
          <td className="py-1 pr-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 opacity-0 group-hover/row:opacity-100 transition-opacity"
              aria-label={`Remove ${row.symbol}`}
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          </td>
        )}
      </tr>
      {expanded && (
        <tr>
          <td colSpan={totalColSpan} className="bg-muted/20 p-4 border-b border-border">
            <ExpandedAssetChart symbol={row.symbol} currency={indicator?.currency} />
          </td>
        </tr>
      )}
    </>
  )
}
