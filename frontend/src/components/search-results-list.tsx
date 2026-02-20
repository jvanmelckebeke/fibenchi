import { Loader2 } from "lucide-react"
import { SearchResultItem } from "@/components/search-result-item"
import { useTrackedSymbols } from "@/hooks/use-tracked-symbols"
import type { SymbolSearchResult } from "@/lib/api"

interface SearchResultsListProps {
  localResults: SymbolSearchResult[] | undefined
  yahooLoading: boolean
  allResults: SymbolSearchResult[]
  /** Currently highlighted index for keyboard navigation (-1 = none). */
  selectedIndex?: number
  onSelect: (result: SymbolSearchResult) => void
  onHover?: (index: number) => void
  /** Extra class name for each row button. */
  rowClassName?: string
  /** Fixed width class for the symbol column. */
  symbolClassName?: string
}

/**
 * Shared two-phase search result list.
 * Renders local results first, then a divider + Yahoo spinner/results.
 */
export function SearchResultsList({
  localResults,
  yahooLoading,
  allResults,
  selectedIndex = -1,
  onSelect,
  onHover,
  rowClassName = "px-4 py-2.5",
  symbolClassName,
}: SearchResultsListProps) {
  const trackedSymbols = useTrackedSymbols()
  const localCount = localResults?.length ?? 0

  return (
    <>
      {allResults.map((r, i) => {
        const isTracked = trackedSymbols.has(r.symbol)
        const isYahooBoundary = i === localCount && localCount > 0
        return (
          <div key={r.symbol}>
            {isYahooBoundary && <div className="border-t border-border my-1" />}
            <button
              className={`flex w-full items-center gap-3 text-sm text-left transition-colors ${rowClassName} ${
                i === selectedIndex
                  ? "bg-primary/10 text-foreground"
                  : "text-foreground hover:bg-muted"
              }`}
              onMouseEnter={() => onHover?.(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onSelect(r)}
            >
              <SearchResultItem result={r} isTracked={isTracked} symbolClassName={symbolClassName} />
            </button>
          </div>
        )
      })}
      {yahooLoading && (
        <>
          {allResults.length > 0 && <div className="border-t border-border my-1" />}
          <div className="flex items-center gap-2 px-4 py-2.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Searching Yahoo Finance…
          </div>
        </>
      )}
    </>
  )
}
