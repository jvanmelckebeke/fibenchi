import { ArrowUp, ArrowDown } from "lucide-react"
import type { GroupSortBy, SortDir } from "@/lib/settings"

export function SortableHeader({
  label,
  sortKey,
  align,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string
  sortKey: GroupSortBy
  align: "left" | "right"
  sortBy?: GroupSortBy
  sortDir?: SortDir
  onSort?: (key: GroupSortBy) => void
}) {
  const active = sortBy === sortKey
  const Icon = active && sortDir === "asc" ? ArrowUp : ArrowDown

  return (
    <th
      className={`${align === "right" ? "text-right" : "text-left"} text-xs font-medium px-2 py-2 whitespace-nowrap ${
        onSort ? "cursor-pointer select-none hover:text-foreground" : ""
      } ${active ? "text-foreground" : "text-muted-foreground"}`}
      onClick={() => onSort?.(sortKey)}
    >
      <span className={`inline-flex items-center gap-0.5 ${align === "right" ? "justify-end" : ""}`}>
        {label}
        {active && <Icon className="h-3 w-3" />}
      </span>
    </th>
  )
}
