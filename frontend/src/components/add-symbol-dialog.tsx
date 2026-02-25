import { useState, useRef } from "react"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SearchResultsList } from "@/components/search-results-list"
import { useCreateAsset, useAddAssetsToGroup, useGroups } from "@/lib/queries"
import { useTwoPhaseSearch } from "@/hooks/use-two-phase-search"

export function AddSymbolDialog({ groupId }: { groupId?: number }) {
  const createAsset = useCreateAsset()
  const addAssetsToGroup = useAddAssetsToGroup()
  const { data: groups } = useGroups()
  const [symbol, setSymbol] = useState("")
  const trimmedQuery = symbol.trim()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [targetGroupId, setTargetGroupId] = useState<number | undefined>(groupId)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  const { localResults, yahooLoading, allResults } = useTwoPhaseSearch(trimmedQuery)

  const hasResults = allResults.length > 0
  const showDropdown = showSuggestions && (hasResults || yahooLoading) && trimmedQuery

  // Non-default groups that can be targeted
  const selectableGroups = groups?.filter((g) => !g.is_default)

  const closeDialog = () => {
    setSymbol("")
    setTargetGroupId(groupId)
    createAsset.reset()
    setDialogOpen(false)
  }

  const handleAdd = () => {
    const s = symbol.trim().toUpperCase()
    if (!s) return
    createAsset.mutate(
      { symbol: s },
      {
        onSuccess: (asset) => {
          const gid = targetGroupId
          if (gid && selectableGroups?.some((g) => g.id === gid)) {
            addAssetsToGroup.mutate(
              { groupId: gid, assetIds: [asset.id] },
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
    <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setSymbol(""); setShowSuggestions(false); setTargetGroupId(groupId); createAsset.reset() } }}>
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
            {showDropdown && (
              <div
                ref={suggestionsRef}
                className="absolute z-50 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-md max-h-72 overflow-auto"
              >
                <SearchResultsList
                  localResults={localResults}
                  yahooLoading={yahooLoading}
                  allResults={allResults}
                  onSelect={(r) => {
                    setSymbol(r.symbol)
                    setShowSuggestions(false)
                  }}
                  rowClassName="px-3 py-2"
                />
              </div>
            )}
            {showSuggestions && !hasResults && !yahooLoading && trimmedQuery && (
              <div className="absolute z-50 top-full left-0 right-0 mt-1 rounded-md border border-border bg-popover shadow-md">
                <div className="px-3 py-2 text-sm text-muted-foreground">No results found</div>
              </div>
            )}
          </div>
          {selectableGroups && selectableGroups.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground shrink-0">Add to</span>
              <Select
                value={targetGroupId?.toString() ?? ""}
                onValueChange={(v) => setTargetGroupId(Number(v))}
              >
                <SelectTrigger size="sm" className="text-xs h-7">
                  <SelectValue placeholder="Select group" />
                </SelectTrigger>
                <SelectContent>
                  {selectableGroups.map((g) => (
                    <SelectItem key={g.id} value={g.id.toString()}>
                      {g.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
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
