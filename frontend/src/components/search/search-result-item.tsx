import { Check } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { SymbolSearchResult } from "@/lib/api"

interface SearchResultItemProps {
  result: SymbolSearchResult
  isTracked: boolean
  /** Additional CSS classes for the symbol span (e.g. fixed width). */
  symbolClassName?: string
}

/**
 * Shared search result row: symbol + name + tracked badge / exchange badge.
 * Render-only -- wrap in your own `<button>` for click handling.
 */
export function SearchResultItem({ result, isTracked, symbolClassName }: SearchResultItemProps) {
  return (
    <>
      <span className={`font-mono font-medium text-primary shrink-0 ${symbolClassName ?? ""}`}>
        {result.symbol}
      </span>
      <span className="text-muted-foreground truncate">{result.name}</span>
      {isTracked ? (
        <Badge variant="outline" className="ml-auto text-xs shrink-0 gap-1 text-emerald-500 border-emerald-500/30">
          <Check className="h-3 w-3" />
          Tracked
        </Badge>
      ) : (
        <Badge variant="secondary" className="ml-auto text-xs shrink-0">
          {result.exchange}
        </Badge>
      )}
    </>
  )
}
