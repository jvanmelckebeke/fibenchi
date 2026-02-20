import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Search } from "lucide-react"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { SearchResultItem } from "@/components/search-result-item"
import { useLocalSearch, useYahooSearch } from "@/lib/queries"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useTrackedSymbols } from "@/hooks/use-tracked-symbols"
import type { SymbolSearchResult } from "@/lib/api"

export function CommandSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const trimmedQuery = query.trim()
  const localQuery = useDebouncedValue(trimmedQuery, 100)
  const yahooQuery = useDebouncedValue(trimmedQuery, 400)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const { data: localResults } = useLocalSearch(localQuery)
  const { data: yahooResults, isFetching: yahooLoading } = useYahooSearch(yahooQuery)
  const trackedSymbols = useTrackedSymbols()

  // Combine local + yahoo for keyboard navigation
  const allResults = useMemo(() => {
    const combined: SymbolSearchResult[] = []
    if (localResults) combined.push(...localResults)
    if (yahooResults) combined.push(...yahooResults)
    return combined
  }, [localResults, yahooResults])

  // Clamp selectedIndex when results shrink
  const clampedIndex = allResults.length > 0 ? Math.min(selectedIndex, allResults.length - 1) : 0

  // Cmd/Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [])

  const handleOpenChange = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen)
    if (nextOpen) {
      setQuery("")
      setSelectedIndex(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [])

  const goToSymbol = useCallback(
    (symbol: string) => {
      setOpen(false)
      navigate(`/asset/${symbol}`)
    },
    [navigate],
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!allResults.length) {
      if (e.key === "Enter" && query.trim()) {
        goToSymbol(query.trim().toUpperCase())
      }
      return
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault()
        setSelectedIndex((i) => (i + 1) % allResults.length)
        break
      case "ArrowUp":
        e.preventDefault()
        setSelectedIndex((i) => (i - 1 + allResults.length) % allResults.length)
        break
      case "Enter":
        e.preventDefault()
        goToSymbol(allResults[clampedIndex].symbol)
        break
    }
  }

  return (
    <>
      <button
        onClick={() => handleOpenChange(true)}
        className="flex items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>Search symbols…</span>
        <kbd className="ml-2 hidden rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono sm:inline-block">
          {navigator.platform?.includes("Mac") ? "⌘" : "Ctrl+"}K
        </kbd>
      </button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-lg p-0 gap-0 overflow-hidden">
          <DialogTitle className="sr-only">Search symbols</DialogTitle>
          <div className="flex items-center border-b px-3">
            <Search className="h-4 w-4 text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search by name or symbol (e.g. AAPL, Tesla)"
              className="flex-1 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>

          {(allResults.length > 0 || yahooLoading) && trimmedQuery && (
            <div className="max-h-72 overflow-auto py-1">
              {allResults.map((r, i) => {
                const isTracked = trackedSymbols.has(r.symbol)
                const isYahooSection = localResults && i === localResults.length && localResults.length > 0
                return (
                  <div key={r.symbol}>
                    {isYahooSection && <div className="border-t border-border my-1" />}
                    <button
                      className={`flex w-full items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${
                        i === clampedIndex
                          ? "bg-primary/10 text-foreground"
                          : "text-foreground hover:bg-muted"
                      }`}
                      onMouseEnter={() => setSelectedIndex(i)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => goToSymbol(r.symbol)}
                    >
                      <SearchResultItem result={r} isTracked={isTracked} symbolClassName="w-16" />
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
            </div>
          )}

          {trimmedQuery && localQuery === trimmedQuery && !yahooLoading && allResults.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              No results found for "{trimmedQuery}"
            </div>
          )}

          {!query.trim() && (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              Type a symbol or company name to search
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
