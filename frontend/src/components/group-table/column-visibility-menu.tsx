import { useMemo } from "react"
import { Settings2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu"
import { getSeriesByField } from "@/lib/indicator-registry"
import { BASE_COLUMN_DEFS, SORTABLE_FIELDS, isColumnVisible } from "./shared"

export function ColumnVisibilityMenu({
  columnSettings,
  onToggle,
}: {
  columnSettings: Record<string, boolean>
  onToggle: (key: string) => void
}) {
  // Build indicator column defs from registry
  const indicatorColumnDefs = useMemo(
    () =>
      SORTABLE_FIELDS.map((field) => {
        const series = getSeriesByField(field)
        return { key: field, label: series?.label ?? field }
      }),
    [],
  )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          aria-label="Toggle column visibility"
        >
          <Settings2 className="h-3.5 w-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>Columns</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {BASE_COLUMN_DEFS.map(({ key, label }) => (
          <DropdownMenuCheckboxItem
            key={key}
            checked={isColumnVisible(columnSettings, key)}
            onCheckedChange={() => onToggle(key)}
            onSelect={(e) => e.preventDefault()}
          >
            {label}
          </DropdownMenuCheckboxItem>
        ))}
        {indicatorColumnDefs.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Indicators</DropdownMenuLabel>
            {indicatorColumnDefs.map(({ key, label }) => (
              <DropdownMenuCheckboxItem
                key={key}
                checked={isColumnVisible(columnSettings, key)}
                onCheckedChange={() => onToggle(key)}
                onSelect={(e) => e.preventDefault()}
              >
                {label}
              </DropdownMenuCheckboxItem>
            ))}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
