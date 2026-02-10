import { useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Trash2, Pencil } from "lucide-react"
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
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(etf.name)
  const [description, setDescription] = useState(etf.description ?? "")

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
          <Link to={`/pseudo-etf/${etf.id}`} className="hover:underline flex-1">
            <CardTitle className="text-base">{etf.name}</CardTitle>
            {etf.description && (
              <p className="text-xs text-muted-foreground mt-1">{etf.description}</p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Base: {etf.base_date} = {etf.base_value} · {etf.constituents.length} constituents
            </p>
          </Link>
        )}
        {!editing && (
          <div className="flex gap-1">
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditing(true)}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => deleteEtf.mutate(etf.id)}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1.5">
          {etf.constituents.map((asset) => (
            <Link key={asset.id} to={`/asset/${asset.symbol}`}>
              <Badge variant="secondary" className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors">
                {asset.symbol}
              </Badge>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
