import { Fragment, type ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import {
  ContextMenu,
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"

interface ContextActionShared {
  label: string
  /** Leading icon (ignored when `swatch` is set). */
  icon?: LucideIcon
  /** Leading colour dot (e.g. a thesis colour) — takes precedence over `icon`. */
  swatch?: string
  disabled?: boolean
  /** Render a separator above this entry (ignored for the first in its menu). */
  separatorBefore?: boolean
}

/** A clickable leaf item. */
export interface ContextActionItem extends ContextActionShared {
  action: () => void
  destructive?: boolean
  /** Muted trailing text (e.g. "AAPL already in group"). */
  hint?: string
}

/** A checkbox toggle (e.g. thesis membership). */
export interface ContextActionCheckbox extends ContextActionShared {
  checked: boolean
  onToggle: (checked: boolean) => void
}

/** A nested submenu of further actions. */
export interface ContextActionSubmenu extends ContextActionShared {
  items: ContextAction[]
  /** Shown (disabled) when `items` is empty. */
  emptyLabel?: string
}

export type ContextAction = ContextActionItem | ContextActionCheckbox | ContextActionSubmenu

const isSubmenu = (a: ContextAction): a is ContextActionSubmenu => "items" in a
const isCheckbox = (a: ContextAction): a is ContextActionCheckbox => "onToggle" in a

function renderItems(actions: ContextAction[]): ReactNode {
  return actions.map((a, i) => {
    const Icon = a.icon
    const lead = a.swatch ? (
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: a.swatch }} />
    ) : Icon ? (
      <Icon className="h-4 w-4" />
    ) : null
    const sep = a.separatorBefore && i > 0 ? <ContextMenuSeparator /> : null

    if (isSubmenu(a)) {
      return (
        <Fragment key={`${a.label}-${i}`}>
          {sep}
          <ContextMenuSub>
            <ContextMenuSubTrigger disabled={a.disabled} className="gap-2">
              {lead}
              {a.label}
            </ContextMenuSubTrigger>
            <ContextMenuSubContent>
              {a.items.length > 0 ? (
                renderItems(a.items)
              ) : a.emptyLabel ? (
                <ContextMenuItem disabled>{a.emptyLabel}</ContextMenuItem>
              ) : null}
            </ContextMenuSubContent>
          </ContextMenuSub>
        </Fragment>
      )
    }

    if (isCheckbox(a)) {
      return (
        <Fragment key={`${a.label}-${i}`}>
          {sep}
          <ContextMenuCheckboxItem
            checked={a.checked}
            disabled={a.disabled}
            onSelect={(e) => e.preventDefault()}
            onCheckedChange={a.onToggle}
          >
            {lead}
            {a.label}
          </ContextMenuCheckboxItem>
        </Fragment>
      )
    }

    return (
      <Fragment key={a.label}>
        {sep}
        <ContextMenuItem
          variant={a.destructive ? "destructive" : undefined}
          disabled={a.disabled}
          onClick={a.action}
        >
          {lead}
          {a.label}
          {a.hint && <span className="ml-auto text-xs text-muted-foreground">{a.hint}</span>}
        </ContextMenuItem>
      </Fragment>
    )
  })
}

/**
 * The menu *content* for an already-established ContextMenu (e.g. a row that owns
 * its own `<ContextMenu>`/trigger and just needs the items). Builds the whole tree
 * — leaves, checkboxes, nested submenus — from a `ContextAction[]`.
 */
export function ContextActionsContent({ actions }: { actions: ContextAction[] }) {
  return <ContextMenuContent>{renderItems(actions)}</ContextMenuContent>
}

/**
 * Wrap any element to make it right-clickable, with the menu generated from a
 * `ContextAction[]`. Renders children untouched when there are no actions, so
 * callers can pass an optional list. (Composition, not inheritance — you wrap an
 * element rather than mixing behaviour into it.)
 */
export function ContextActionable({
  actions,
  children,
  asChild = true,
}: {
  actions?: ContextAction[]
  children: ReactNode
  /** Forward the trigger onto the child element (default) vs. a wrapper span. */
  asChild?: boolean
}) {
  if (!actions || actions.length === 0) return <>{children}</>
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild={asChild}>{children}</ContextMenuTrigger>
      <ContextActionsContent actions={actions} />
    </ContextMenu>
  )
}
