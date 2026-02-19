import { useState, useMemo, forwardRef } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import {
  Star,
  Plus,
  X,
  Trash2,
  Pencil,
  GripVertical,
} from "lucide-react"
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
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { useGroups, useCreateGroup, useDeleteGroup, useReorderGroups } from "@/lib/queries"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { Input } from "@/components/ui/input"
import { resolveIcon } from "@/lib/icon-utils"
import { EditGroupDialog } from "@/components/edit-group-dialog"
import type { Group } from "@/lib/api"

/** Drag handle rendered inside the sidebar menu button. */
const DragHandle = forwardRef<HTMLButtonElement, React.ComponentProps<"button">>(
  (props, ref) => (
    <button
      ref={ref}
      type="button"
      className="cursor-grab touch-none text-muted-foreground/50 hover:text-muted-foreground -ml-1 shrink-0"
      tabIndex={-1}
      {...props}
    >
      <GripVertical className="h-3.5 w-3.5" />
    </button>
  ),
)
DragHandle.displayName = "DragHandle"

function SortableGroupItem({
  group,
  isActive,
  showDragHandle,
  onEdit,
  onDelete,
}: {
  group: Group
  isActive: boolean
  showDragHandle: boolean
  onEdit: () => void
  onDelete: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: group.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const GroupIcon = useMemo(() => resolveIcon(group.icon), [group.icon])

  return (
    <SidebarMenuItem ref={setNodeRef} style={style}>
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <div className="flex items-center w-full">
            {showDragHandle && <DragHandle {...attributes} {...listeners} />}
            <SidebarMenuButton
              asChild
              isActive={isActive}
              tooltip={group.name}
            >
              <Link to={`/groups/${group.id}`}>
                {/* eslint-disable-next-line react-hooks/static-components -- resolveIcon returns stable refs from lucide's icon map */}
                <GroupIcon />
                <span>{group.name}</span>
              </Link>
            </SidebarMenuButton>
            {group.assets.length > 0 && (
              <SidebarMenuBadge>{group.assets.length}</SidebarMenuBadge>
            )}
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem onClick={onEdit}>
            <Pencil />
            Edit group
          </ContextMenuItem>
          <ContextMenuSeparator />
          <ContextMenuItem
            variant="destructive"
            onClick={onDelete}
          >
            <Trash2 />
            Delete group
          </ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>
    </SidebarMenuItem>
  )
}

export function GroupsSection() {
  const { data: groups } = useGroups()
  const createGroup = useCreateGroup()
  const deleteGroup = useDeleteGroup()
  const reorderGroups = useReorderGroups()
  const location = useLocation()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null)
  const [editTarget, setEditTarget] = useState<Group | null>(null)
  const { state } = useSidebar()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    createGroup.mutate(
      { name },
      {
        onSuccess: (group) => {
          setNewName("")
          setCreating(false)
          navigate(`/groups/${group.id}`)
        },
      },
    )
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    const id = deleteTarget.id
    deleteGroup.mutate(id, {
      onSuccess: () => {
        if (location.pathname === `/groups/${id}`) navigate("/")
        setDeleteTarget(null)
      },
      onError: () => setDeleteTarget(null),
    })
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !groups) return

    const allIds = groups.map((g) => g.id)
    const oldIndex = allIds.indexOf(active.id as number)
    const newIndex = allIds.indexOf(over.id as number)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = [...allIds]
    reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, active.id as number)
    reorderGroups.mutate(reordered)
  }

  if (!groups) return null

  const defaultGroup = groups.find((g) => g.is_default)
  const customGroups = groups.filter((g) => !g.is_default)
  const isCollapsed = state === "collapsed"

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Groups</SidebarGroupLabel>
      {!isCollapsed && customGroups.length > 0 && (
        <SidebarGroupAction
          onClick={() => setEditing(!editing)}
          title={editing ? "Done" : "Edit groups"}
        >
          {editing ? <X /> : <Pencil />}
        </SidebarGroupAction>
      )}
      <SidebarGroupContent>
        <SidebarMenu>
          {defaultGroup && (
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname === `/groups/${defaultGroup.id}` ||
                  location.pathname === "/watchlist"
                }
                tooltip={defaultGroup.name}
              >
                <Link to={`/groups/${defaultGroup.id}`}>
                  <Star />
                  <span>{defaultGroup.name}</span>
                </Link>
              </SidebarMenuButton>
              {defaultGroup.assets.length > 0 && (
                <SidebarMenuBadge>{defaultGroup.assets.length}</SidebarMenuBadge>
              )}
            </SidebarMenuItem>
          )}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={customGroups.map((g) => g.id)}
              strategy={verticalListSortingStrategy}
            >
              {customGroups.map((group) => (
                <SortableGroupItem
                  key={group.id}
                  group={group}
                  isActive={location.pathname === `/groups/${group.id}`}
                  showDragHandle={editing}
                  onEdit={() => setEditTarget(group)}
                  onDelete={() => setDeleteTarget({ id: group.id, name: group.name })}
                />
              ))}
            </SortableContext>
          </DndContext>
          {!isCollapsed && (
            <SidebarMenuItem>
              {creating ? (
                <div className="px-2 py-1">
                  <Input
                    placeholder="Group name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreate()
                      if (e.key === "Escape") {
                        setCreating(false)
                        setNewName("")
                      }
                    }}
                    onBlur={() => {
                      if (!newName.trim()) {
                        setCreating(false)
                        setNewName("")
                      }
                    }}
                    autoFocus
                    className="h-7 text-xs"
                  />
                </div>
              ) : (
                <SidebarMenuButton
                  className="text-muted-foreground"
                  onClick={() => setCreating(true)}
                >
                  <Plus className="h-4 w-4" />
                  <span>New group</span>
                </SidebarMenuButton>
              )}
            </SidebarMenuItem>
          )}
        </SidebarMenu>
      </SidebarGroupContent>

      <EditGroupDialog
        group={editTarget}
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete group</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.name}&rdquo;? Assets in this group will not be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SidebarGroup>
  )
}
