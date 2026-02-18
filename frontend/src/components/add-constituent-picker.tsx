import { useState } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  useAssets,
  useAddPseudoEtfConstituents,
  useCreateAsset,
} from "@/lib/queries"

export function AddConstituentPicker({
  etfId,
  existingIds,
  onClose,
}: {
  etfId: number
  existingIds: number[]
  onClose: () => void
}) {
  const { data: allAssets } = useAssets()
  const addConstituents = useAddPseudoEtfConstituents()
  const createAsset = useCreateAsset()
  const available = allAssets?.filter((a) => !existingIds.includes(a.id)) ?? []
  const [selected, setSelected] = useState<number[]>([])
  const [newTicker, setNewTicker] = useState("")
  const [tickerError, setTickerError] = useState("")

  const toggle = (id: number) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleAdd = () => {
    if (!selected.length) return
    addConstituents.mutate({ etfId, assetIds: selected }, { onSuccess: () => onClose() })
  }

  const handleNewTicker = () => {
    const sym = newTicker.trim().toUpperCase()
    if (!sym) return
    setTickerError("")
    createAsset.mutate(
      { symbol: sym, add_to_default_group: false },
      {
        onSuccess: (asset) => {
          addConstituents.mutate(
            { etfId, assetIds: [asset.id] },
            { onSuccess: () => { setNewTicker(""); onClose() } }
          )
        },
        onError: (err) => setTickerError(err.message),
      }
    )
  }

  return (
    <div className="p-3 rounded-md border bg-muted/30 space-y-3">
      <div className="flex gap-2 items-center">
        <Input
          placeholder="New ticker (e.g. AAPL)"
          value={newTicker}
          onChange={(e) => { setNewTicker(e.target.value); setTickerError("") }}
          onKeyDown={(e) => e.key === "Enter" && handleNewTicker()}
          className="w-48"
        />
        <Button size="sm" onClick={handleNewTicker} disabled={!newTicker.trim() || createAsset.isPending}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          {createAsset.isPending ? "Adding..." : "Add new"}
        </Button>
        {tickerError && <span className="text-xs text-destructive">{tickerError}</span>}
      </div>

      {available.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground">Or pick existing assets:</p>
          <div className="flex flex-wrap gap-1.5">
            {available.map((a) => (
              <Badge
                key={a.id}
                variant={selected.includes(a.id) ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => toggle(a.id)}
              >
                {a.symbol}
              </Badge>
            ))}
          </div>
        </>
      )}

      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
        {selected.length > 0 && (
          <Button size="sm" onClick={handleAdd} disabled={addConstituents.isPending}>
            Add ({selected.length})
          </Button>
        )}
      </div>
    </div>
  )
}
