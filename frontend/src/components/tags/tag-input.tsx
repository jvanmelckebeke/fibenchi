import { useState } from "react"
import { ComboCreateInput } from "@/components/combo-create-input"
import { ColorSwatchPicker } from "@/components/color-swatch-picker"
import { DEFAULT_THESIS_COLOR } from "@/lib/thesis-colors"
import type { TagBrief } from "@/lib/api"
import { useTags, useCreateTag, useAttachTag, useDetachTag } from "@/lib/queries"

export function TagInput({
  symbol,
  currentTags,
}: {
  symbol: string
  currentTags: TagBrief[]
}) {
  const [search, setSearch] = useState("")
  const [newColor, setNewColor] = useState(DEFAULT_THESIS_COLOR)

  const { data: allTags } = useTags()
  const createTag = useCreateTag()
  const attachTag = useAttachTag()
  const detachTag = useDetachTag()

  return (
    <ComboCreateInput<TagBrief>
      label="Tags"
      placeholder="Add tag..."
      search={search}
      onSearchChange={setSearch}
      current={currentTags}
      onRemove={(t) => detachTag.mutate({ symbol, tagId: t.id })}
      options={allTags ?? []}
      onSelect={(t) => {
        attachTag.mutate({ symbol, tagId: t.id })
        setSearch("")
      }}
      create={{
        extras: <ColorSwatchPicker value={newColor} onChange={setNewColor} size="sm" />,
        label: (s) => (
          <>
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: newColor }} />
            Create &ldquo;{s}&rdquo;
          </>
        ),
        onCreate: (s) =>
          createTag.mutateAsync({ name: s.toLowerCase(), color: newColor }).then((tag) => {
            attachTag.mutate({ symbol, tagId: tag.id })
            setSearch("")
          }),
      }}
    />
  )
}
