import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { IconPicker } from "@/components/icon-picker"
import { ColorSwatchPicker } from "@/components/color-swatch-picker"
import type { ThesisStatus } from "@/lib/api"

export interface ThesisFormValues {
  name: string
  color: string
  icon: string
  status: ThesisStatus
  openedAt: string
  description: string
}

const STATUSES: { value: ThesisStatus; label: string }[] = [
  { value: "watching", label: "Watching" },
  { value: "live", label: "Live" },
  { value: "played_out", label: "Played out" },
]

/**
 * The shared body of the new/edit thesis dialogs: name + icon, colour, status,
 * opened date and hypothesis. Controlled — the parent owns the state and the
 * mutation (create vs. update differ enough that only the fields are shared).
 * `idPrefix` keeps `htmlFor` ids unique between simultaneously-mountable dialogs.
 */
export function ThesisFormFields({
  values,
  onChange,
  idPrefix,
  namePlaceholder,
}: {
  values: ThesisFormValues
  onChange: <K extends keyof ThesisFormValues>(key: K, value: ThesisFormValues[K]) => void
  idPrefix: string
  namePlaceholder?: string
}) {
  return (
    <div className="space-y-4 py-2">
      <div className="space-y-2">
        <Label htmlFor={`${idPrefix}-name`}>Name</Label>
        <div className="flex gap-2">
          <IconPicker value={values.icon} onChange={(v) => onChange("icon", v)} />
          <Input
            id={`${idPrefix}-name`}
            value={values.name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder={namePlaceholder}
            className="flex-1"
            autoFocus
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Colour</Label>
        <ColorSwatchPicker value={values.color} onChange={(c) => onChange("color", c)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}-status`}>Status</Label>
          <Select value={values.status} onValueChange={(v) => onChange("status", v as ThesisStatus)}>
            <SelectTrigger id={`${idPrefix}-status`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${idPrefix}-opened`}>Opened</Label>
          <Input
            id={`${idPrefix}-opened`}
            type="date"
            value={values.openedAt}
            onChange={(e) => onChange("openedAt", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${idPrefix}-desc`}>Hypothesis</Label>
        <Textarea
          id={`${idPrefix}-desc`}
          value={values.description}
          onChange={(e) => onChange("description", e.target.value)}
          placeholder="What's the thesis? (optional)"
        />
      </div>
    </div>
  )
}
