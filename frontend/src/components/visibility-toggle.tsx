import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { INDICATOR_REGISTRY, isIndicatorVisible } from "@/lib/indicator-registry"

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
  idPrefix,
  onChange,
}: {
  visibility: Record<string, boolean>
  idPrefix: string
  onChange: (id: string, visible: boolean) => void
}) {
  return (
    <>
      {INDICATOR_REGISTRY.map((desc) => (
        <VisibilityToggle
          key={`${idPrefix}-${desc.id}`}
          id={`${idPrefix}-${desc.id}`}
          label={desc.label}
          checked={isIndicatorVisible(visibility, desc.id)}
          onCheckedChange={(v) => onChange(desc.id, v)}
        />
      ))}
    </>
  )
}
