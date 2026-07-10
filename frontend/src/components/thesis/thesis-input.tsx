import { useState } from "react"
import { ComboCreateInput } from "@/components/combo-create-input"
import { NewThesisDialog } from "@/components/thesis/new-thesis-dialog"
import { useTheses, useAddAssetToThesis, useRemoveAssetFromThesis } from "@/lib/queries"
import type { Thesis } from "@/lib/api"

export function ThesisInput({ assetId }: { assetId: number }) {
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: allTheses } = useTheses()
  const addToThesis = useAddAssetToThesis()
  const removeFromThesis = useRemoveAssetFromThesis()

  const theses = allTheses ?? []
  const current = theses.filter((t) => t.assets.some((a) => a.id === assetId))

  return (
    <>
      <ComboCreateInput<Thesis>
        label="Theses"
        placeholder="Add to thesis..."
        search={search}
        onSearchChange={setSearch}
        current={current}
        onRemove={(t) => removeFromThesis.mutate({ thesisId: t.id, assetId })}
        options={theses}
        onSelect={(t) => {
          addToThesis.mutate({ thesisId: t.id, assetId })
          setSearch("")
        }}
        renderCreate={(s, close) => (
          <div className="border-t p-1">
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent text-muted-foreground"
              onClick={() => {
                close()
                setDialogOpen(true)
              }}
            >
              + New thesis &ldquo;{s}&rdquo;&hellip;
            </button>
          </div>
        )}
      />
      <NewThesisDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        initialName={search.trim()}
        onCreated={(thesis) => {
          addToThesis.mutate({ thesisId: thesis.id, assetId })
          setSearch("")
        }}
      />
    </>
  )
}
