// Fibenchi's read on a ticker, offered rather than applied.
//
// Two registers, and the difference is who decided:
//
//   - A field Fibenchi guessed (`disagrees`) gets a banner with an apply
//     action. It's still only a suggestion — nothing changes until clicked.
//   - A field *you* set (`differs` minus `disagrees`) gets one muted line and
//     a way back to auto. No banner, no nagging: you already decided. But it
//     stays visible and reversible, because "don't argue with you" shouldn't
//     collapse into "never speak again" — which is exactly what happens if
//     the recommendation disappears the moment you touch the field.
//
// Wording is `Suggestion: Index · Points` rather than a sentence: this is a
// form of labels and values, and prose reads as chatter next to them.

import { Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { AssetSuggestion, AssetType, UnitKind } from "@/lib/api"

const TYPE_LABEL: Record<AssetType, string> = {
  stock: "Stock",
  etf: "ETF",
  index: "Index",
}

const UNIT_LABEL: Record<UnitKind, string> = {
  currency: "Currency",
  percent: "Percent",
  points: "Points",
}

/** Only the parts under dispute, so the line never restates what the form
 * already agrees with. */
function summarise(suggestion: AssetSuggestion, fields: string[]): string {
  const parts: string[] = []
  if (fields.includes("type")) parts.push(TYPE_LABEL[suggestion.type])
  if (fields.includes("unit_kind")) parts.push(UNIT_LABEL[suggestion.unit_kind])
  return parts.join(" · ")
}

export function AssetSuggestionBanner({
  suggestion,
  onApply,
  onReset,
  resetPending,
}: {
  suggestion: AssetSuggestion | null | undefined
  onApply: () => void
  onReset: () => void
  resetPending?: boolean
}) {
  if (!suggestion?.differs.length) return null

  const open = suggestion.disagrees
  // Fields you set that the shape still reads differently. Shown, not pushed.
  const owned = suggestion.differs.filter((f) => !open.includes(f))

  return (
    <div className="space-y-2">
      {open.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-[12px]">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <div className="flex-1 space-y-1.5">
            <p className="leading-snug text-muted-foreground">
              Suggestion:{" "}
              <span className="font-medium text-foreground">{summarise(suggestion, open)}</span>
            </p>
            <Button type="button" variant="outline" size="sm" className="h-6 px-2 text-[11px]" onClick={onApply}>
              Use this
            </Button>
          </div>
        </div>
      )}
      {owned.length > 0 && (
        <p className="px-0.5 text-[11px] leading-snug text-muted-foreground">
          Suggestion: <span className="text-foreground">{summarise(suggestion, owned)}</span>
          {" — "}
          <button
            type="button"
            onClick={onReset}
            disabled={resetPending}
            className="underline underline-offset-2 hover:text-foreground disabled:opacity-50"
          >
            reset to auto-detect
          </button>
        </p>
      )}
    </div>
  )
}
