import { useState } from "react"
import { Trash2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useUpdateThesis, useDeleteThesis } from "@/lib/queries"
import type { Thesis, ThesisStatus } from "@/lib/api"

const PRESET_COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"]

const STATUSES: { value: ThesisStatus; label: string }[] = [
  { value: "watching", label: "Watching" },
  { value: "live", label: "Live" },
  { value: "played_out", label: "Played out" },
]

interface EditThesisDialogProps {
  thesis: Thesis | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditThesisDialog({ thesis, open, onOpenChange }: EditThesisDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {thesis && (
          <EditThesisForm key={thesis.id} thesis={thesis} onClose={() => onOpenChange(false)} />
        )}
      </DialogContent>
    </Dialog>
  )
}

function EditThesisForm({ thesis, onClose }: { thesis: Thesis; onClose: () => void }) {
  const updateThesis = useUpdateThesis(thesis.id)
  const deleteThesis = useDeleteThesis()
  const [name, setName] = useState(thesis.name)
  const [color, setColor] = useState(thesis.color)
  const [status, setStatus] = useState<ThesisStatus>(thesis.status)
  const [openedAt, setOpenedAt] = useState(thesis.opened_at)
  const [description, setDescription] = useState(thesis.description ?? "")
  const [confirmDelete, setConfirmDelete] = useState(false)

  const handleSave = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    updateThesis.mutate(
      {
        name: trimmed,
        color,
        status,
        opened_at: openedAt,
        description: description.trim() || null,
      },
      { onSuccess: onClose },
    )
  }

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    deleteThesis.mutate(thesis.id, { onSuccess: onClose })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit thesis</DialogTitle>
      </DialogHeader>
      <div className="space-y-4 py-2">
        <div className="space-y-2">
          <Label htmlFor="edit-thesis-name">Name</Label>
          <Input
            id="edit-thesis-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </div>
        <div className="space-y-2">
          <Label>Colour</Label>
          <div className="flex gap-1.5">
            {PRESET_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`Colour ${c}`}
                className={`h-6 w-6 rounded-full border-2 ${color === c ? "border-foreground" : "border-transparent"}`}
                style={{ backgroundColor: c }}
                onClick={() => setColor(c)}
              />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="edit-thesis-status">Status</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as ThesisStatus)}>
              <SelectTrigger id="edit-thesis-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-thesis-opened">Opened</Label>
            <Input
              id="edit-thesis-opened"
              type="date"
              value={openedAt}
              onChange={(e) => setOpenedAt(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="edit-thesis-desc">Hypothesis</Label>
          <Textarea
            id="edit-thesis-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What's the thesis? (optional)"
          />
        </div>
      </div>
      <DialogFooter className="sm:justify-between">
        <Button
          variant="ghost"
          className="gap-1.5 text-destructive hover:text-destructive"
          onClick={handleDelete}
          disabled={deleteThesis.isPending}
        >
          <Trash2 className="h-4 w-4" />
          {confirmDelete ? "Confirm delete" : "Delete"}
        </Button>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={!name.trim() || updateThesis.isPending}>
            Save
          </Button>
        </div>
      </DialogFooter>
    </>
  )
}
