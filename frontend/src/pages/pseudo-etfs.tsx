import { useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Trash2, Pencil, X, UserPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
  usePseudoEtfs,
  useCreatePseudoEtf,
  useUpdatePseudoEtf,
  useDeletePseudoEtf,
  useAssets,
  useAddPseudoEtfConstituents,
  useRemovePseudoEtfConstituent,
} from "@/lib/queries"
import type { PseudoETF } from "@/lib/api"

export function PseudoEtfsPage() {
  const { data: etfs, isLoading } = usePseudoEtfs()
  const [creating, setCreating] = useState(false)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Pseudo-ETFs</h1>
        <Button onClick={() => setCreating(true)} disabled={creating}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Pseudo-ETF
        </Button>
      </div>

      {creating && <CreateForm onClose={() => setCreating(false)} />}

      {isLoading && <p className="text-muted-foreground">Loading...</p>}

      {etfs && etfs.length === 0 && !creating && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <p>No pseudo-ETFs yet. Create one to track a custom basket of stocks.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {etfs?.map((etf) => (
          <EtfCard key={etf.id} etf={etf} />
        ))}
      </div>
    </div>
  )
}

function CreateForm({ onClose }: { onClose: () => void }) {
  const create = useCreatePseudoEtf()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [baseDate, setBaseDate] = useState("")

  const handleSubmit = () => {
    if (!name.trim() || !baseDate) return
    create.mutate(
      { name: name.trim(), description: description.trim() || undefined, base_date: baseDate },
      { onSuccess: () => onClose() }
    )
  }

  return (
    <Card>
      <CardContent className="pt-6 space-y-3">
        <Input
          placeholder="Name (e.g. Quantum Computing)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <Textarea
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="min-h-[60px]"
        />
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Base date:</label>
          <Input
            type="date"
            value={baseDate}
            onChange={(e) => setBaseDate(e.target.value)}
            className="w-44"
          />
          <span className="text-xs text-muted-foreground">Indexed to 100 at this date</span>
        </div>
        {create.isError && <p className="text-sm text-destructive">{create.error.message}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={create.isPending}>Create</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function EtfCard({ etf }: { etf: PseudoETF }) {
  const deleteEtf = useDeletePseudoEtf()
  const updateEtf = useUpdatePseudoEtf()
  const removeConstituent = useRemovePseudoEtfConstituent()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(etf.name)
  const [description, setDescription] = useState(etf.description ?? "")
  const [addingAsset, setAddingAsset] = useState(false)

  const handleSave = () => {
    updateEtf.mutate(
      { id: etf.id, data: { name: name.trim(), description: description.trim() || undefined } },
      { onSuccess: () => setEditing(false) }
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between pb-2">
        {editing ? (
          <div className="flex-1 space-y-2 mr-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[40px]"
            />
            <div className="flex gap-1">
              <Button size="sm" onClick={handleSave}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <div>
            <Link to={`/pseudo-etf/${etf.id}`} className="hover:underline">
              <CardTitle className="text-base">{etf.name}</CardTitle>
            </Link>
            {etf.description && (
              <p className="text-xs text-muted-foreground mt-1">{etf.description}</p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Base: {etf.base_date} = {etf.base_value}
            </p>
          </div>
        )}
        {!editing && (
          <div className="flex gap-1">
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setAddingAsset(!addingAsset)}>
              <UserPlus className="h-3.5 w-3.5" />
            </Button>
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditing(true)}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => deleteEtf.mutate(etf.id)}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {addingAsset && (
          <AddConstituentPicker
            etfId={etf.id}
            existingIds={etf.constituents.map((a) => a.id)}
            onClose={() => setAddingAsset(false)}
          />
        )}

        {etf.constituents.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No constituents. Add stocks to this basket.</p>
        )}

        <div className="flex flex-wrap gap-2">
          {etf.constituents.map((asset) => (
            <div key={asset.id} className="flex items-center gap-1 group/asset">
              <Link to={`/asset/${asset.symbol}`}>
                <Badge variant="secondary" className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors">
                  {asset.symbol}
                </Badge>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 opacity-0 group-hover/asset:opacity-100 transition-opacity"
                onClick={() => removeConstituent.mutate({ etfId: etf.id, assetId: asset.id })}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>

        {etf.constituents.length > 0 && (
          <Link to={`/pseudo-etf/${etf.id}`}>
            <Button variant="outline" size="sm" className="mt-2">
              View Performance
            </Button>
          </Link>
        )}
      </CardContent>
    </Card>
  )
}

function AddConstituentPicker({
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
  const available = allAssets?.filter((a) => !existingIds.includes(a.id)) ?? []
  const [selected, setSelected] = useState<number[]>([])

  const toggle = (id: number) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleAdd = () => {
    if (!selected.length) return
    addConstituents.mutate({ etfId, assetIds: selected }, { onSuccess: () => onClose() })
  }

  return (
    <div className="p-3 rounded-md border bg-muted/30 space-y-2">
      {available.length === 0 ? (
        <p className="text-sm text-muted-foreground">No more assets to add. Add assets from the dashboard first.</p>
      ) : (
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
      )}
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
        <Button size="sm" onClick={handleAdd} disabled={!selected.length || addConstituents.isPending}>
          Add ({selected.length})
        </Button>
      </div>
    </div>
  )
}
