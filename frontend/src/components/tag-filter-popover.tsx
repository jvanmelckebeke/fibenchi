import { Filter, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { TagBadge } from "@/components/tag-badge"
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
        <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5">
          <Filter className="h-3.5 w-3.5" />
          Tags
          {activeCount > 0 && (
            <span className="bg-primary text-primary-foreground rounded-full px-1.5 py-0 text-[10px] font-semibold leading-4 min-w-[18px] text-center">
              {activeCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto max-w-80">
        <div className="flex items-center justify-between gap-4 mb-2">
          <span className="text-xs font-medium text-muted-foreground">Filter by tag</span>
          {activeCount > 0 && (
            <button
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              onClick={onClear}
            >
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
