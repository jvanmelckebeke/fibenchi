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
import { IconPicker } from "@/components/icon-picker"
import { useUpdateGroup } from "@/lib/queries"
import type { Group } from "@/lib/api"

interface EditGroupDialogProps {
  group: Group | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function EditGroupForm({ group, onClose }: { group: Group; onClose: () => void }) {
  const updateGroup = useUpdateGroup()
  const [name, setName] = useState(group.name)
  const [description, setDescription] = useState(group.description ?? "")
  const [icon, setIcon] = useState(group.icon ?? "folder")

  const handleSave = () => {
    if (!name.trim()) return
    updateGroup.mutate(
      { id: group.id, data: { name: name.trim(), description: description.trim() || undefined, icon } },
      { onSuccess: onClose },
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit group</DialogTitle>
      </DialogHeader>
      <div className="space-y-4 py-2">
        <div className="space-y-2">
          <Label htmlFor="group-name">Name</Label>
          <div className="flex gap-2">
            <IconPicker value={icon} onChange={setIcon} />
            <Input
              id="group-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
              className="flex-1"
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="group-desc">Description</Label>
          <Textarea
            id="group-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description..."
            rows={3}
            className="resize-none text-sm"
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} disabled={!name.trim() || updateGroup.isPending}>
          Save
        </Button>
      </DialogFooter>
    </>
  )
}

export function EditGroupDialog({ group, open, onOpenChange }: EditGroupDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        {group && (
          <EditGroupForm
            key={group.id}
            group={group}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
