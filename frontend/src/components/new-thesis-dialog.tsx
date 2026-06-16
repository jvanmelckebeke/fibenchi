import { useState } from "react"
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
import { useCreateThesis } from "@/lib/queries"
import type { Thesis, ThesisStatus } from "@/lib/api"

const PRESET_COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"]

const STATUSES: { value: ThesisStatus; label: string }[] = [
  { value: "watching", label: "Watching" },
  { value: "live", label: "Live" },
  { value: "played_out", label: "Played out" },
]

function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

interface NewThesisDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Pre-fill the name field (e.g. from a "Create X…" affordance). */
  initialName?: string
  /** Called with the created thesis — use to immediately assign a ticker. */
  onCreated?: (thesis: Thesis) => void
}

export function NewThesisDialog({ open, onOpenChange, initialName, onCreated }: NewThesisDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {open && (
          <NewThesisForm
            key={initialName ?? ""}
            initialName={initialName}
            onClose={() => onOpenChange(false)}
            onCreated={onCreated}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function NewThesisForm({
  initialName,
  onClose,
  onCreated,
}: {
  initialName?: string
  onClose: () => void
  onCreated?: (thesis: Thesis) => void
}) {
  const createThesis = useCreateThesis()
  const [name, setName] = useState(initialName ?? "")
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [status, setStatus] = useState<ThesisStatus>("watching")
  const [openedAt, setOpenedAt] = useState(todayISO())
  const [description, setDescription] = useState("")

  const handleCreate = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    createThesis.mutate(
      {
        name: trimmed,
        color,
        status,
        opened_at: openedAt,
        description: description.trim() || undefined,
      },
      {
        onSuccess: (thesis) => {
          onCreated?.(thesis)
          onClose()
        },
      },
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>New thesis</DialogTitle>
      </DialogHeader>
      <div className="space-y-4 py-2">
        <div className="space-y-2">
          <Label htmlFor="thesis-name">Name</Label>
          <Input
            id="thesis-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. El Niño"
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
            <Label htmlFor="thesis-status">Status</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as ThesisStatus)}>
              <SelectTrigger id="thesis-status">
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
            <Label htmlFor="thesis-opened">Opened</Label>
            <Input
              id="thesis-opened"
              type="date"
              value={openedAt}
              onChange={(e) => setOpenedAt(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="thesis-desc">Hypothesis</Label>
          <Textarea
            id="thesis-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What's the thesis? (optional)"
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={handleCreate} disabled={!name.trim() || createThesis.isPending}>
          Create
        </Button>
      </DialogFooter>
    </>
  )
}
