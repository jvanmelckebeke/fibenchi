import { useState } from "react"
import { AlertTriangle } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { useAssetAttachments, useHardDeleteAsset, useRemoveAssetFromGroup } from "@/lib/queries"
import type { Asset, AssetAttachments } from "@/lib/api"

interface RemoveAssetDialogProps {
  asset: Asset | null
  groupId: number
  groupName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** The non-empty attachments a hard delete would cascade into. */
function attachmentLines(a: AssetAttachments): { label: string; value: string }[] {
  const lines: { label: string; value: string }[] = []
  if (a.theses.length) lines.push({ label: "Theses", value: a.theses.join(", ") })
  if (a.pseudo_etfs.length) lines.push({ label: "Pseudo-ETFs", value: a.pseudo_etfs.join(", ") })
  if (a.tags.length) lines.push({ label: "Tags", value: a.tags.join(", ") })
  if (a.has_note) lines.push({ label: "Note", value: "yes" })
  if (a.annotation_count > 0) lines.push({ label: "Annotations", value: String(a.annotation_count) })
  return lines
}

/**
 * Confirms removing an asset from a group. When this is the asset's *last* group,
 * it warns that the asset becomes an invisible orphan, lists what stays attached
 * (theses / pseudo-ETFs / tags / note / annotations), and offers a hard delete —
 * so the lifecycle decision is made with the attachments in view (see #536).
 */
export function RemoveAssetDialog({ asset, groupId, groupName, open, onOpenChange }: RemoveAssetDialogProps) {
  const symbol = asset?.symbol ?? ""
  const { data: attachments, isLoading } = useAssetAttachments(symbol, open && asset != null)
  const [alsoDelete, setAlsoDelete] = useState(false)
  const removeFromGroup = useRemoveAssetFromGroup()
  const hardDelete = useHardDeleteAsset()

  // Reset the hard-delete opt-in on every close, so a reopen starts unchecked.
  const setOpen = (o: boolean) => {
    if (!o) setAlsoDelete(false)
    onOpenChange(o)
  }

  // Removing from this group orphans the asset when it's the only group it's in.
  const willOrphan = attachments != null && attachments.groups.length <= 1
  const pending = removeFromGroup.isPending || hardDelete.isPending
  const lines = attachments ? attachmentLines(attachments) : []

  const confirm = () => {
    if (!asset) return
    const done = () => setOpen(false)
    if (alsoDelete) hardDelete.mutate(asset.symbol, { onSuccess: done })
    else removeFromGroup.mutate({ groupId, assetId: asset.id }, { onSuccess: done })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Remove {symbol}?</DialogTitle>
          <DialogDescription>
            Remove <span className="font-medium text-foreground">{symbol}</span> from{" "}
            <span className="font-medium text-foreground">{groupName}</span>.
          </DialogDescription>
        </DialogHeader>

        {isLoading && <p className="text-sm text-muted-foreground">Checking attachments…</p>}

        {willOrphan && (
          <div className="space-y-3">
            <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <p>
                <span className="font-medium">{symbol}</span> will no longer be in any group — it
                becomes an invisible orphan, still tracked by its other attachments.
              </p>
            </div>
            {lines.length > 0 && (
              <div className="rounded-md border border-border p-3 text-sm">
                <p className="mb-1 text-xs text-muted-foreground">Still attached to:</p>
                <ul className="space-y-0.5">
                  {lines.map((l) => (
                    <li key={l.label}>
                      <span className="text-muted-foreground">{l.label}:</span> {l.value}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <label htmlFor="also-delete-entirely" className="flex cursor-pointer items-start gap-2 text-sm">
              <Checkbox
                id="also-delete-entirely"
                checked={alsoDelete}
                onCheckedChange={(v) => setAlsoDelete(v === true)}
                className="mt-0.5"
              />
              <span>
                Also delete <span className="font-medium">{symbol}</span> entirely — removes it from
                all groups, theses and pseudo-ETFs and deletes its note, tags and annotations. This
                can’t be undone.
              </span>
            </label>
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant={alsoDelete ? "destructive" : "default"}
            onClick={confirm}
            disabled={pending || isLoading}
          >
            {alsoDelete ? "Delete entirely" : "Remove"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
