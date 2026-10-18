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
      <span className={`shrink-0 font-mono font-medium text-primary ${symbolClassName ?? ""}`}>
        {result.symbol}
      </span>
      <span className="truncate text-muted-foreground">{result.name}</span>
      {isTracked ? (
        <Badge
          variant="outline"
          className="ml-auto shrink-0 gap-1 border-emerald-500/30 text-xs text-emerald-500">
          <Check className="h-3 w-3" />
          Tracked
        </Badge>
      ) : (
        <Badge variant="secondary" className="ml-auto shrink-0 text-xs">
          {result.exchange}
        </Badge>
      )}
    </>
  )
}
