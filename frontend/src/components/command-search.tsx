import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { Search } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { useSymbolSearch } from "@/lib/queries"

export function CommandSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const prevResultsRef = useRef<string>("")
  const { data: results } = useSymbolSearch(debouncedQuery)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query])

  // Reset selection when results change (derived — no effect needed)
  const resultsKey = useMemo(() => results?.map((r) => r.symbol).join(",") ?? "", [results])
  if (resultsKey !== prevResultsRef.current) {
    prevResultsRef.current = resultsKey
    if (selectedIndex !== 0) setSelectedIndex(0)
  }

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
      setDebouncedQuery("")
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
    if (!results?.length) {
      if (e.key === "Enter" && query.trim()) {
        goToSymbol(query.trim().toUpperCase())
      }
      return
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault()
        setSelectedIndex((i) => (i + 1) % results.length)
        break
      case "ArrowUp":
        e.preventDefault()
        setSelectedIndex((i) => (i - 1 + results.length) % results.length)
        break
      case "Enter":
        e.preventDefault()
        goToSymbol(results[selectedIndex].symbol)
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

          {results && results.length > 0 && query.trim() && (
            <div className="max-h-72 overflow-auto py-1">
              {results.map((r, i) => (
                <button
                  key={r.symbol}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${
                    i === selectedIndex
                      ? "bg-primary/10 text-foreground"
                      : "text-foreground hover:bg-muted"
                  }`}
                  onMouseEnter={() => setSelectedIndex(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => goToSymbol(r.symbol)}
                >
                  <span className="font-mono font-medium text-primary shrink-0 w-16">
                    {r.symbol}
                  </span>
                  <span className="text-muted-foreground truncate">{r.name}</span>
                  <Badge variant="secondary" className="ml-auto text-xs shrink-0">
                    {r.exchange}
                  </Badge>
                </button>
              ))}
            </div>
          )}

          {query.trim() && debouncedQuery && results && results.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              No results found for "{query.trim()}"
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
