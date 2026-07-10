import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { ThesisFormFields, type ThesisFormValues } from "@/components/thesis/thesis-form-fields"
import { useCreateThesis } from "@/lib/queries"
import { DEFAULT_THESIS_COLOR } from "@/lib/thesis-colors"
import type { Thesis } from "@/lib/api"

function todayISO(): string {
  // Local calendar date as yyyy-mm-dd (en-CA), NOT UTC — toISOString() can roll
  // to tomorrow in the evening for users west of UTC.
  return new Date().toLocaleDateString("en-CA")
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
  const [values, setValues] = useState<ThesisFormValues>({
    name: initialName ?? "",
    color: DEFAULT_THESIS_COLOR,
    icon: "briefcase",
    status: "watching",
    openedAt: todayISO(),
    description: "",
  })
  const update: <K extends keyof ThesisFormValues>(key: K, value: ThesisFormValues[K]) => void =
    (key, value) => setValues((v) => ({ ...v, [key]: value }))

  const handleCreate = () => {
    const trimmed = values.name.trim()
    if (!trimmed) return
    createThesis.mutate(
      {
        name: trimmed,
        color: values.color,
        icon: values.icon,
        status: values.status,
        opened_at: values.openedAt,
        description: values.description.trim() || undefined,
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
      <ThesisFormFields values={values} onChange={update} idPrefix="thesis" namePlaceholder="e.g. El Niño" />
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={handleCreate} disabled={!values.name.trim() || createThesis.isPending}>
          Create
        </Button>
      </DialogFooter>
    </>
  )
}
