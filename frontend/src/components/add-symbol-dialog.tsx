import { useState, useEffect, useRef } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useCreateAsset, useSymbolSearch } from "@/lib/queries"

export function AddSymbolDialog() {
  const createAsset = useCreateAsset()
  const [symbol, setSymbol] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const { data: searchResults } = useSymbolSearch(debouncedQuery)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(symbol.trim()), 300)
    return () => clearTimeout(timer)
  }, [symbol])

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate(
      { symbol: s },
      {
        onSuccess: () => {
          setSymbol("")
          setDialogOpen(false)
        },
      },
    )
  }

  return (
    <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setSymbol(""); setShowSuggestions(false); createAsset.reset() } }}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" />
          Add Symbol
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Symbol</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="relative">
            <Input
              placeholder="Search by name or symbol (e.g. AAPL, Porsche)"
              value={symbol}
              onChange={(e) => { setSymbol(e.target.value); setShowSuggestions(true) }}
              onKeyDown={(e) => { if (e.key === "Enter") { setShowSuggestions(false); handleAdd() } }}
              onFocus={() => setShowSuggestions(true)}
              autoFocus
            />
            {showSuggestions && searchResults && searchResults.length > 0 && symbol.trim() && (
              <div
                ref={suggestionsRef}
                className="absolute z-50 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-md max-h-60 overflow-auto"
              >
                {searchResults.map((r) => (
                  <button
                    key={r.symbol}
                    type="button"
                    className="flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => { setSymbol(r.symbol); setShowSuggestions(false) }}
                  >
                    <span className="font-mono font-medium text-primary shrink-0">{r.symbol}</span>
                    <span className="text-muted-foreground truncate">{r.name}</span>
                    <Badge variant="secondary" className="ml-auto text-xs shrink-0">{r.exchange}</Badge>
                  </button>
                ))}
              </div>
            )}
          </div>
          {createAsset.isError && (
            <p className="text-sm text-destructive">{createAsset.error.message}</p>
          )}
          <div className="flex justify-end">
            <Button onClick={() => { setShowSuggestions(false); handleAdd() }} disabled={createAsset.isPending || !symbol.trim()}>
              {createAsset.isPending ? "Adding…" : "Add"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
