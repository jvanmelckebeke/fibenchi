import { Filter, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TagBadge } from "@/components/tags/tag-badge"
import type { Tag } from "@/lib/api"

interface TagFilterPopoverProps {
  tags: Tag[]
  selectedTags: number[]
  onToggleTag: (id: number) => void
  onClear: () => void
}

export function TagFilterPopover({
  tags,
  selectedTags,
  onToggleTag,
  onClear,
}: TagFilterPopoverProps) {
  const activeCount = selectedTags.length

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 gap-1.5 text-xs">
          <Filter className="h-3.5 w-3.5" />
          Tags
          {activeCount > 0 && (
            <span className="min-w-[18px] rounded-full bg-primary px-1.5 py-0 text-center text-[10px] leading-4 font-semibold text-primary-foreground">
              {activeCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto max-w-80">
        <div className="mb-2 flex items-center justify-between gap-4">
          <span className="text-xs font-medium text-muted-foreground">Filter by tag</span>
          {activeCount > 0 && (
            <button
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              onClick={onClear}>
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <TagBadge
              key={tag.id}
              name={tag.name}
              color={tag.color}
              active={activeCount === 0 || selectedTags.includes(tag.id)}
              onClick={() => onToggleTag(tag.id)}
            />
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
