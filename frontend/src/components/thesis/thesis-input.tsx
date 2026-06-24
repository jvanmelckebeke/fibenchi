import { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { TagBadge } from "@/components/tags/tag-badge"
import { NewThesisDialog } from "@/components/thesis/new-thesis-dialog"
import { useTheses, useAddAssetToThesis, useRemoveAssetFromThesis } from "@/lib/queries"

export function ThesisInput({ assetId }: { assetId: number }) {
  const [search, setSearch] = useState("")
  const [open, setOpen] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data: allTheses } = useTheses()
  const addToThesis = useAddAssetToThesis()
  const removeFromThesis = useRemoveAssetFromThesis()

  const theses = allTheses ?? []
  const current = theses.filter((t) => t.assets.some((a) => a.id === assetId))
  const currentIds = new Set(current.map((t) => t.id))
  const filtered = theses.filter(
    (t) => !currentIds.has(t.id) && t.name.toLowerCase().includes(search.toLowerCase()),
  )
  const exactMatch = theses.some((t) => t.name.toLowerCase() === search.trim().toLowerCase())

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleAttach = (thesisId: number) => {
    addToThesis.mutate({ thesisId, assetId })
    setSearch("")
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Theses</h3>
      <div className="flex flex-wrap gap-1.5">
        {current.map((t) => (
          <TagBadge
            key={t.id}
            name={t.name}
            color={t.color}
            onRemove={() => removeFromThesis.mutate({ thesisId: t.id, assetId })}
          />
        ))}
      </div>
      <div ref={ref} className="relative">
        <Input
          placeholder="Add to thesis..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
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
              {filtered.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => handleAttach(t.id)}
                >
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: t.color }} />
                  {t.name}
                </button>
              ))}
              {search.trim() && !exactMatch && (
                <div className="border-t p-1">
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent text-muted-foreground"
                    onClick={() => {
                      setOpen(false)
                      setDialogOpen(true)
                    }}
                  >
                    + New thesis &ldquo;{search.trim()}&rdquo;&hellip;
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      <NewThesisDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        initialName={search.trim()}
        onCreated={(thesis) => {
          addToThesis.mutate({ thesisId: thesis.id, assetId })
          setSearch("")
        }}
      />
    </div>
  )
}
