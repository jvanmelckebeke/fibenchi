import { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { TagBadge } from "@/components/tag-badge"
import type { TagBrief } from "@/lib/api"
import { useTags, useCreateTag, useAttachTag, useDetachTag } from "@/lib/queries"

const PRESET_COLORS = [
  "#3b82f6", // blue
  "#ef4444", // red
  "#22c55e", // green
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#f97316", // orange
]

export function TagInput({
  symbol,
  currentTags,
}: {
  symbol: string
  currentTags: TagBrief[]
}) {
  const [search, setSearch] = useState("")
  const [open, setOpen] = useState(false)
  const [newColor, setNewColor] = useState(PRESET_COLORS[0])
  const ref = useRef<HTMLDivElement>(null)

  const { data: allTags } = useTags()
  const createTag = useCreateTag()
  const attachTag = useAttachTag()
  const detachTag = useDetachTag()

  const currentIds = new Set(currentTags.map((t) => t.id))
  const filtered = (allTags ?? []).filter(
    (t) => !currentIds.has(t.id) && t.name.toLowerCase().includes(search.toLowerCase())
  )
  const exactMatch = (allTags ?? []).some((t) => t.name.toLowerCase() === search.toLowerCase())

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleAttach = (tagId: number) => {
    attachTag.mutate({ symbol, tagId })
    setSearch("")
    setOpen(false)
  }

  const handleCreate = () => {
    const name = search.trim().toLowerCase()
    if (!name) return
    createTag.mutate(
      { name, color: newColor },
      {
        onSuccess: (tag) => {
          attachTag.mutate({ symbol, tagId: tag.id })
          setSearch("")
          setOpen(false)
        },
      }
    )
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Tags</h3>
      <div className="flex flex-wrap gap-1.5">
        {currentTags.map((tag) => (
          <TagBadge
            key={tag.id}
            name={tag.name}
            color={tag.color}
            onRemove={() => detachTag.mutate({ symbol, tagId: tag.id })}
          />
        ))}
      </div>
      <div ref={ref} className="relative">
        <Input
          placeholder="Add tag..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          className="h-8 text-sm"
        />
        {open && (search || filtered.length > 0) && (
          <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
            <div className="max-h-48 overflow-y-auto p-1">
              {filtered.map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => handleAttach(tag.id)}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: tag.color }}
                  />
                  {tag.name}
                </button>
              ))}
              {search.trim() && !exactMatch && (
                <div className="border-t p-2 space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      {PRESET_COLORS.map((c) => (
                        <button
                          key={c}
                          type="button"
                          className={`h-4 w-4 rounded-full border-2 ${
                            newColor === c ? "border-foreground" : "border-transparent"
                          }`}
                          style={{ backgroundColor: c }}
                          onClick={() => setNewColor(c)}
                        />
                      ))}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent text-muted-foreground"
                    onClick={handleCreate}
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: newColor }}
                    />
                    Create &ldquo;{search.trim()}&rdquo;
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
