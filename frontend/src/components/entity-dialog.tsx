import { Fragment, type ReactNode } from "react"
import { Dialog, DialogContent } from "@/components/ui/dialog"

/**
 * A modal that renders an inner form only when an entity is present, remounting
 * it (via `key={entity.id}`) whenever the entity changes so the form's local
 * `useState` re-seeds from the new props. Centralises the wrapper idiom shared
 * by the edit-asset / edit-group / edit-thesis dialogs.
 */
export function EntityDialog<T extends { id: number }>({
  entity,
  open,
  onOpenChange,
  contentClassName,
  children,
}: {
  entity: T | null
  open: boolean
  onOpenChange: (open: boolean) => void
  contentClassName?: string
  /** Renders the inner form; `close` dismisses the dialog. */
  children: (entity: T, close: () => void) => ReactNode
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={contentClassName}>
        {entity && (
          <Fragment key={entity.id}>
            {children(entity, () => onOpenChange(false))}
          </Fragment>
        )}
      </DialogContent>
    </Dialog>
  )
}
