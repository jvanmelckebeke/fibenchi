import { useState } from "react"
import { Trash2 } from "lucide-react"
import { DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { EntityDialog } from "@/components/entity-dialog"
import { ThesisFormFields, type ThesisFormValues } from "@/components/thesis/thesis-form-fields"
import { useUpdateThesis, useDeleteThesis } from "@/lib/queries"
import type { Thesis } from "@/lib/api"

interface EditThesisDialogProps {
  thesis: Thesis | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditThesisDialog({ thesis, open, onOpenChange }: EditThesisDialogProps) {
  return (
    <EntityDialog entity={thesis} open={open} onOpenChange={onOpenChange}>
      {(thesis, close) => <EditThesisForm thesis={thesis} onClose={close} />}
    </EntityDialog>
  )
}

function EditThesisForm({ thesis, onClose }: { thesis: Thesis; onClose: () => void }) {
  const updateThesis = useUpdateThesis(thesis.id)
  const deleteThesis = useDeleteThesis()
  const [values, setValues] = useState<ThesisFormValues>({
    name: thesis.name,
    color: thesis.color,
    icon: thesis.icon ?? "briefcase",
    status: thesis.status,
    openedAt: thesis.opened_at,
    description: thesis.description ?? "",
  })
  const [confirmDelete, setConfirmDelete] = useState(false)
  const update: <K extends keyof ThesisFormValues>(key: K, value: ThesisFormValues[K]) => void =
    (key, value) => setValues((v) => ({ ...v, [key]: value }))

  const handleSave = () => {
    const trimmed = values.name.trim()
    if (!trimmed) return
    updateThesis.mutate(
      {
        name: trimmed,
        color: values.color,
        icon: values.icon,
        status: values.status,
        opened_at: values.openedAt,
        description: values.description.trim() || null,
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
      <ThesisFormFields values={values} onChange={update} idPrefix="edit-thesis" />
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
          <Button onClick={handleSave} disabled={!values.name.trim() || updateThesis.isPending}>
            Save
          </Button>
        </div>
      </DialogFooter>
    </>
  )
}
