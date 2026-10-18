import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import type { Annotation, AnnotationCreate } from "@/lib/api"

interface AnnotationsListProps {
  annotations: Annotation[] | undefined
  onCreate: (data: AnnotationCreate) => void
  onDelete: (id: number) => void
  isCreating: boolean
}

export function AnnotationsList({
  annotations,
  onCreate,
  onDelete,
  isCreating,
}: AnnotationsListProps) {
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ date: "", title: "", body: "", color: "#3b82f6" })

  const handleAdd = () => {
    if (!form.date || !form.title) return
    onCreate({
      date: form.date,
      title: form.title,
      body: form.body || undefined,
      color: form.color,
    })
    setForm({ date: "", title: "", body: "", color: "#3b82f6" })
    setAdding(false)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Annotations</CardTitle>
        <Button size="sm" variant="ghost" onClick={() => setAdding(!adding)}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {adding && (
          <div className="space-y-2 rounded-md border bg-muted/30 p-3">
            <div className="flex gap-2">
              <Input
                type="date"
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
                className="w-40"
              />
              <Input
                placeholder="Title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                className="h-9 w-9 cursor-pointer rounded border"
              />
            </div>
            <Textarea
              placeholder="Notes (optional)"
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
              className="min-h-[60px]"
            />
            <div className="flex justify-end gap-1">
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleAdd} disabled={isCreating}>
                Save
              </Button>
            </div>
          </div>
        )}

        {annotations?.length === 0 && !adding && (
          <p className="text-sm text-muted-foreground italic">No annotations yet.</p>
        )}

        {annotations?.map((a) => (
          <div key={a.id} className="group flex items-start gap-3">
            <div
              className="mt-1.5 h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: a.color }}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{a.title}</span>
                <Badge variant="secondary" className="text-xs">
                  {a.date}
                </Badge>
              </div>
              {a.body && <p className="mt-0.5 text-xs text-muted-foreground">{a.body}</p>}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
              aria-label="Delete annotation"
              onClick={() => onDelete(a.id)}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
