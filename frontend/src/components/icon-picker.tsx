import { useState, useMemo } from "react"
import { icons, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toKebab, resolveIcon } from "@/lib/icon-utils"

/** Curated icons shown by default before searching. */
const CURATED_ICONS = [
  "Folder", "FolderOpen", "Briefcase", "Globe", "TrendingUp",
  "BarChart3", "LineChart", "PieChart", "Wallet", "Landmark",
  "Building2", "Factory", "Cpu", "Zap", "Leaf",
  "Heart", "Shield", "Lock", "Gem", "Crown",
  "Rocket", "Target", "Flag", "Bookmark", "Star",
  "Sun", "Moon", "Cloud", "Flame", "Droplets",
  "Car", "Plane", "Ship", "Home", "Store",
  "Smartphone", "Monitor", "Gamepad2", "Music", "Film",
] as const

interface IconPickerProps {
  value: string | null
  onChange: (iconName: string) => void
}

export function IconPicker({ value, onChange }: IconPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")

  const allIconNames = useMemo(() => Object.keys(icons), [])

  const displayedIcons = useMemo(() => {
    if (!search.trim()) return [...CURATED_ICONS]
    const q = search.toLowerCase()
    return allIconNames.filter((name) => name.toLowerCase().includes(q)).slice(0, 60)
  }, [search, allIconNames])

  const SelectedIcon = useMemo(() => resolveIcon(value), [value])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" className="h-9 w-9 shrink-0">
          {/* eslint-disable-next-line react-hooks/static-components -- resolveIcon returns stable refs from lucide's icon map */}
          <SelectedIcon className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-2" align="start">
        <Input
          placeholder="Search icons..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mb-2 h-8 text-xs"
          autoFocus
        />
        <ScrollArea className="h-[200px]">
          <div className="grid grid-cols-8 gap-1">
            {displayedIcons.map((name) => {
              const Icon = icons[name as keyof typeof icons] as LucideIcon | undefined
              if (!Icon) return null
              const kebab = toKebab(name)
              const isSelected = value === kebab
              return (
                <button
                  key={name}
                  type="button"
                  title={name}
                  className={`flex items-center justify-center rounded p-1.5 hover:bg-accent ${
                    isSelected ? "bg-accent ring-1 ring-primary" : ""
                  }`}
                  onClick={() => {
                    onChange(kebab)
                    setOpen(false)
                    setSearch("")
                  }}
                >
                  <Icon className="h-4 w-4" />
                </button>
              )
            })}
          </div>
          {displayedIcons.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">No icons found</p>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}
