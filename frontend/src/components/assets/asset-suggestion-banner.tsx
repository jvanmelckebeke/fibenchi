// Fibenchi's read on a ticker, offered rather than applied.
//
// The banner only appears when the backend says a field is still
// auto-detected *and* disagrees with what's stored — a value you chose never
// produces one, however much the ticker's shape argues otherwise. That's the
// whole point of the provenance flag: it decides whether we're allowed to
// bring this up, not whether we're allowed to overwrite you. Nothing changes
// until Apply, which is an ordinary edit like any other.

import { Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { AssetSuggestion, AssetType, UnitKind } from "@/lib/api"

const TYPE_LABEL: Record<AssetType, string> = {
  stock: "a stock",
  etf: "an ETF",
  index: "an index",
}

const UNIT_LABEL: Record<UnitKind, string> = {
  currency: "a price",
  percent: "a rate, in percent",
  points: "a level, in points",
}

/** "an index quoted as a level, in points" — only the parts under dispute, so
 * the sentence never states something the form already agrees with. */
function phrase(suggestion: AssetSuggestion): string {
  const parts: string[] = []
  if (suggestion.disagrees.includes("type")) parts.push(TYPE_LABEL[suggestion.type])
  if (suggestion.disagrees.includes("unit_kind")) parts.push(`quoted as ${UNIT_LABEL[suggestion.unit_kind]}`)
  return parts.join(", ")
}

export function AssetSuggestionBanner({
  symbol,
  suggestion,
  onApply,
}: {
  symbol: string
  suggestion: AssetSuggestion | null | undefined
  onApply: () => void
}) {
  if (!suggestion?.disagrees.length) return null

  return (
    <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-[12px]">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <div className="flex-1 space-y-1.5">
        <p className="leading-snug text-muted-foreground">
          Fibenchi reads <span className="font-medium text-foreground">{symbol}</span> as{" "}
          <span className="font-medium text-foreground">{phrase(suggestion)}</span>.
        </p>
        <Button type="button" variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={onApply}>
          Use this
        </Button>
      </div>
    </div>
  )
}
