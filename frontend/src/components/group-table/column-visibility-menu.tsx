import { useMemo } from "react"
import { Settings2, GripVertical } from "lucide-react"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  arrayMove,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover"
import { getSeriesByField } from "@/lib/indicator-registry"
import { BASE_COLUMN_DEFS, isColumnVisible } from "./shared"

interface ColumnVisibilityMenuProps {
  columnSettings: Record<string, boolean>
  onToggle: (key: string) => void
  responsiveHidden: Set<string>
  /** All indicator field ids in the user's persisted order (drag reorders these). */
  orderedIndicatorFields: string[]
  onReorder: (nextOrder: string[]) => void
}

/** A draggable indicator row: grip handle + visibility checkbox + label. */
function SortableIndicatorRow({
  field,
  label,
  checked,
  narrow,
  onToggle,
}: {
  field: string
  label: string
  checked: boolean
  narrow: boolean
  onToggle: (key: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: field })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded px-1 py-1 hover:bg-accent"
    >
      <button
        type="button"
        aria-label={`Reorder ${label} column`}
        className="cursor-grab touch-none text-muted-foreground/50 hover:text-muted-foreground shrink-0"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      <Checkbox
        id={`col-${field}`}
        checked={checked}
        disabled={narrow}
        onCheckedChange={() => onToggle(field)}
      />
      <Label
        htmlFor={`col-${field}`}
        className="flex flex-1 items-center justify-between gap-2 text-sm font-normal"
      >
        {label}
        {narrow && <span className="text-[10px] text-muted-foreground">narrow</span>}
      </Label>
    </div>
  )
}

export function ColumnVisibilityMenu({
  columnSettings,
  onToggle,
  responsiveHidden,
  orderedIndicatorFields,
  onReorder,
}: ColumnVisibilityMenuProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const indicatorLabels = useMemo(() => {
    const map: Record<string, string> = {}
    for (const field of orderedIndicatorFields) {
      map[field] = getSeriesByField(field)?.label ?? field
    }
    return map
  }, [orderedIndicatorFields])

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = orderedIndicatorFields.indexOf(active.id as string)
    const newIndex = orderedIndicatorFields.indexOf(over.id as string)
    if (oldIndex === -1 || newIndex === -1) return
    onReorder(arrayMove(orderedIndicatorFields, oldIndex, newIndex))
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          aria-label="Configure columns"
        >
          <Settings2 className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56 gap-2 p-2">
        <div className="px-1 text-xs font-medium text-muted-foreground">Columns</div>
        <div className="flex flex-col">
          {BASE_COLUMN_DEFS.map(({ key, label }) => (
            <div key={key} className="flex items-center gap-2 rounded px-1 py-1 hover:bg-accent">
              {/* Spacer aligns base-column checkboxes with the draggable rows below. */}
              <span className="w-3.5 shrink-0" aria-hidden />
              <Checkbox
                id={`col-${key}`}
                checked={isColumnVisible(columnSettings, key)}
                onCheckedChange={() => onToggle(key)}
              />
              <Label htmlFor={`col-${key}`} className="flex-1 text-sm font-normal">
                {label}
              </Label>
            </div>
          ))}
        </div>
        {orderedIndicatorFields.length > 0 && (
          <>
            <Separator className="my-1" />
            <div className="px-1 text-xs font-medium text-muted-foreground">Indicators</div>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={orderedIndicatorFields}
                strategy={verticalListSortingStrategy}
              >
                <div className="flex flex-col">
                  {orderedIndicatorFields.map((field) => (
                    <SortableIndicatorRow
                      key={field}
                      field={field}
                      label={indicatorLabels[field]}
                      checked={isColumnVisible(columnSettings, field)}
                      narrow={responsiveHidden.has(field)}
                      onToggle={onToggle}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}
