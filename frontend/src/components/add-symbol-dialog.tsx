import { useState, useRef } from "react"
import { useNavigate } from "react-router-dom"
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
import { SearchResultItem } from "@/components/search-result-item"
import { useCreateAsset, useAddAssetsToGroup, useSymbolSearch } from "@/lib/queries"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useTrackedSymbols } from "@/hooks/use-tracked-symbols"

export function AddSymbolDialog({ groupId, isDefaultGroup }: { groupId?: number; isDefaultGroup?: boolean }) {
  const navigate = useNavigate()
  const createAsset = useCreateAsset()
  const addAssetsToGroup = useAddAssetsToGroup()
  const trackedSymbols = useTrackedSymbols()
  const [symbol, setSymbol] = useState("")
  const debouncedQuery = useDebouncedValue(symbol.trim(), 300)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const { data: searchResults } = useSymbolSearch(debouncedQuery)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  const closeDialog = () => {
    setSymbol("")
    setDialogOpen(false)
  }

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate(
      { symbol: s },
      {
        onSuccess: (asset) => {
          // If on a non-default group page, also add to that group
          if (groupId && !isDefaultGroup) {
            addAssetsToGroup.mutate(
              { groupId, assetIds: [asset.id] },
              { onSuccess: closeDialog },
            )
          } else {
            closeDialog()
          }
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
                {searchResults.map((r) => {
                  const isTracked = trackedSymbols.has(r.symbol)
                  return (
                    <button
                      key={r.symbol}
                      type="button"
                      className="flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        if (isTracked) {
                          setDialogOpen(false)
                          navigate(`/asset/${r.symbol}`)
                        } else {
                          setSymbol(r.symbol)
                          setShowSuggestions(false)
                        }
                      }}
                    >
                      <SearchResultItem result={r} isTracked={isTracked} />
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          {createAsset.isError && (
            <p className="text-sm text-destructive">{createAsset.error.message}</p>
          )}
          <div className="flex justify-end">
            <Button onClick={() => { setShowSuggestions(false); handleAdd() }} disabled={createAsset.isPending || addAssetsToGroup.isPending || !symbol.trim()}>
              {createAsset.isPending || addAssetsToGroup.isPending ? "Adding\u2026" : "Add"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
