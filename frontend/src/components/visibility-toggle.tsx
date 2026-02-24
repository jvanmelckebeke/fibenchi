import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { INDICATOR_REGISTRY, type Placement } from "@/lib/indicator-registry"
import { isEnabledForContext } from "@/lib/settings"

export function VisibilityToggle({
  id,
  label,
  checked,
  onCheckedChange,
}: {
  id: string
  label: string
  checked: boolean
  onCheckedChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <Label htmlFor={id}>{label}</Label>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  )
}

export function IndicatorVisibilitySection({
  visibility,
  contextPlacements,
  idPrefix,
  onChange,
}: {
  visibility: Record<string, Placement[]>
  contextPlacements: Placement[]
  idPrefix: string
  onChange: (id: string, visible: boolean) => void
}) {
  return (
    <>
      {INDICATOR_REGISTRY.filter((desc) =>
        desc.capabilities.some((c) => contextPlacements.includes(c)),
      ).map((desc) => (
        <VisibilityToggle
          key={`${idPrefix}-${desc.id}`}
          id={`${idPrefix}-${desc.id}`}
          label={desc.label}
          checked={isEnabledForContext(visibility, desc.id, contextPlacements)}
          onCheckedChange={(v) => onChange(desc.id, v)}
        />
      ))}
    </>
  )
}
