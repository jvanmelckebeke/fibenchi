import { ArrowUp, ArrowDown } from "lucide-react"
import type { GroupSortBy, SortDir } from "@/lib/settings"

export function SortableHeader({
  label,
  sortKey,
  align,
  sortBy,
  sortDir,
  onSort,
  style,
  onResizeStart,
  onResizeReset,
}: {
  label: string
  sortKey: GroupSortBy
  align: "left" | "right"
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
  style?: React.CSSProperties
  onResizeStart?: (e: React.PointerEvent) => void
  onResizeReset?: (e: React.MouseEvent) => void
}) {
  const active = sortBy === sortKey
  const Icon = active && sortDir === "asc" ? ArrowUp : ArrowDown

  return (
    <th
      className={`relative ${align === "right" ? "text-right" : "text-left"} text-xs font-medium px-3 py-2 ${
        onSort ? "cursor-pointer select-none hover:text-foreground" : ""
      } ${active ? "text-foreground" : "text-muted-foreground"}`}
      onClick={() => onSort?.(sortKey)}
      style={style}
    >
      <span className={`inline-flex items-center gap-0.5 ${align === "right" ? "justify-end" : ""}`}>
        {label}
        {active && <Icon className="h-3 w-3" />}
      </span>
      {onResizeStart && (
        <button
          type="button"
          aria-label={`Resize ${label} column`}
          tabIndex={-1}
          className="absolute right-0 top-1 bottom-1 w-1 cursor-col-resize bg-border/50 hover:bg-primary/40 transition-colors border-0 p-0"
          onPointerDown={onResizeStart}
          onDoubleClick={onResizeReset}
          onClick={(e) => e.stopPropagation()}
        />
      )}
    </th>
  )
}
