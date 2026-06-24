import { useRef, useState, useEffect, type ReactNode } from "react"
import { Input } from "@/components/ui/input"
import { TagBadge } from "@/components/tags/tag-badge"

export interface ComboItem {
  id: number
  name: string
  color: string
}

/**
 * A combobox that lists existing `{id,name,color}` entities (filtered by a
 * search box), shows the currently-selected ones as removable badges, and
 * offers a "create new" affordance via the `renderCreate` render-prop. Shared
 * by the tag and thesis inputs, which previously hand-rolled identical
 * click-outside / dropdown / row markup.
 *
 * Search is controlled by the caller (so create flows can read the typed text,
 * e.g. to seed a "New thesis" dialog name). Open state is owned internally.
 */
export function ComboCreateInput<T extends ComboItem>({
  label,
  placeholder,
  search,
  onSearchChange,
  current,
  onRemove,
  options,
  onSelect,
  renderCreate,
}: {
  label: string
  placeholder: string
  search: string
  onSearchChange: (s: string) => void
  /** Already-selected entities, rendered as removable badges. */
  current: T[]
  onRemove: (item: T) => void
  /** All candidate entities; filtered internally by search and not-already-current. */
  options: T[]
  onSelect: (item: T) => void
  /** Create-new footer; receives the trimmed search and a fn to close the dropdown. */
  renderCreate?: (search: string, close: () => void) => ReactNode
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const currentIds = new Set(current.map((c) => c.id))
  const q = search.trim().toLowerCase()
  const filtered = options.filter((o) => !currentIds.has(o.id) && o.name.toLowerCase().includes(q))
  const exactMatch = options.some((o) => o.name.toLowerCase() === q)
  const close = () => setOpen(false)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{label}</h3>
      <div className="flex flex-wrap gap-1.5">
        {current.map((item) => (
          <TagBadge key={item.id} name={item.name} color={item.color} onRemove={() => onRemove(item)} />
        ))}
      </div>
      <div ref={ref} className="relative">
        <Input
          placeholder={placeholder}
          value={search}
          onChange={(e) => {
            onSearchChange(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setOpen(false)
              ;(e.target as HTMLInputElement).blur()
            }
          }}
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          className="h-8 text-sm"
        />
        {open && (search || filtered.length > 0) && (
          <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md" role="listbox">
            <div className="max-h-48 overflow-y-auto p-1">
              {filtered.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => {
                    onSelect(item)
                    setOpen(false)
                  }}
                >
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.name}
                </button>
              ))}
              {search.trim() && !exactMatch && renderCreate?.(search.trim(), close)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
