import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { useCreatePseudoEtf } from "@/lib/queries"

export function CreateForm({ onClose }: { onClose: () => void }) {
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
          <label htmlFor="pseudo-etf-base-date" className="text-sm text-muted-foreground">Base date:</label>
          <Input
            id="pseudo-etf-base-date"
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
