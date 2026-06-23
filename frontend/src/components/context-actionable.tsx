import { Fragment, type ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"

export interface ContextAction {
  label: string
  action: () => void
  icon?: LucideIcon
  destructive?: boolean
  disabled?: boolean
  /** Render a separator above this item (ignored for the first item). */
  separatorBefore?: boolean
}

/**
 * Wrap any element to give it a right-click menu generated from a flat list of
 * actions — keeps menu markup out of caller props. Renders its children
 * untouched when there are no actions, so callers can pass an optional list.
 *
 * This deliberately models *flat* action lists. Menus with submenus, checkboxes
 * or grouping (e.g. the group/thesis row menus) build a `ContextMenuContent` by
 * hand instead — forcing those into a data model would cost more than it saves.
 */
export function ContextActionable({
  actions,
  children,
  asChild = true,
}: {
  actions?: ContextAction[]
  children: ReactNode
  /** Forward the menu trigger onto the child element (default) vs. a wrapper span. */
  asChild?: boolean
}) {
  if (!actions || actions.length === 0) return <>{children}</>

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild={asChild}>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        {actions.map((a, i) => {
          const Icon = a.icon
          return (
            <Fragment key={a.label}>
              {a.separatorBefore && i > 0 && <ContextMenuSeparator />}
              <ContextMenuItem
                variant={a.destructive ? "destructive" : undefined}
                disabled={a.disabled}
                onClick={a.action}
              >
                {Icon && <Icon className="h-4 w-4" />}
                {a.label}
              </ContextMenuItem>
            </Fragment>
          )
        })}
      </ContextMenuContent>
    </ContextMenu>
  )
}
