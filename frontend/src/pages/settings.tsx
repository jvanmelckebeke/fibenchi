import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useSettings, type AppSettings, type GroupViewMode } from "@/lib/settings"
import { INDICATOR_REGISTRY } from "@/lib/indicator-registry"

function VisibilityToggle({
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

export function SettingsPage() {
  const { settings, updateSettings } = useSettings()
  const [draft, setDraft] = useState<AppSettings>(settings)

  const isDirty = JSON.stringify(draft) !== JSON.stringify(settings)

  const change = (patch: Partial<AppSettings>) => {
    setDraft((prev) => ({ ...prev, ...patch }))
  }

  const apply = () => {
    updateSettings(draft)
  }

  const discard = () => {
    setDraft(settings)
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Group View</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Default View</Label>
            <Select
              value={draft.group_view_mode}
              onValueChange={(v) => change({ group_view_mode: v as GroupViewMode })}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="card">Card</SelectItem>
                <SelectItem value="table">Table</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <VisibilityToggle
            id="wl-sparkline"
            label="Sparkline Chart"
            checked={draft.group_show_sparkline}
            onCheckedChange={(v) => change({ group_show_sparkline: v })}
          />
          {INDICATOR_REGISTRY.map((desc) => (
            <VisibilityToggle
              key={`grp-${desc.id}`}
              id={`grp-${desc.id}`}
              label={desc.label}
              checked={draft.group_indicator_visibility[desc.id] !== false}
              onCheckedChange={(v) =>
                change({
                  group_indicator_visibility: { ...draft.group_indicator_visibility, [desc.id]: v },
                })
              }
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Detail Page Chart</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {INDICATOR_REGISTRY.map((desc) => (
            <VisibilityToggle
              key={`dtl-${desc.id}`}
              id={`dtl-${desc.id}`}
              label={desc.label}
              checked={draft.detail_indicator_visibility[desc.id] !== false}
              onCheckedChange={(v) =>
                change({
                  detail_indicator_visibility: { ...draft.detail_indicator_visibility, [desc.id]: v },
                })
              }
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Chart Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <VisibilityToggle
            id="sync-crosshairs"
            label="Sync Pseudo-ETF Crosshairs"
            checked={draft.sync_pseudo_etf_crosshairs}
            onCheckedChange={(v) => change({ sync_pseudo_etf_crosshairs: v })}
          />
          <div className="flex items-center justify-between">
            <Label>Default Period</Label>
            <Select
              value={draft.chart_default_period}
              onValueChange={(v) => change({ chart_default_period: v })}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1mo">1M</SelectItem>
                <SelectItem value="3mo">3M</SelectItem>
                <SelectItem value="6mo">6M</SelectItem>
                <SelectItem value="1y">1Y</SelectItem>
                <SelectItem value="2y">2Y</SelectItem>
                <SelectItem value="5y">5Y</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between">
            <Label>Chart Type</Label>
            <Select
              value={draft.chart_type}
              onValueChange={(v) => change({ chart_type: v as "candle" | "line" })}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="candle">Candlestick</SelectItem>
                <SelectItem value="line">Line</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Display</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Theme</Label>
            <Select
              value={draft.theme}
              onValueChange={(v) => change({ theme: v as "dark" | "light" | "system" })}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">System</SelectItem>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <VisibilityToggle
            id="compact"
            label="Compact Mode"
            checked={draft.compact_mode}
            onCheckedChange={(v) => change({ compact_mode: v })}
          />
          <div className="flex items-center justify-between">
            <Label>Decimal Places</Label>
            <Select
              value={String(draft.decimal_places)}
              onValueChange={(v) => change({ decimal_places: Number(v) })}
            >
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">0</SelectItem>
                <SelectItem value="1">1</SelectItem>
                <SelectItem value="2">2</SelectItem>
                <SelectItem value="3">3</SelectItem>
                <SelectItem value="4">4</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
      </div>

      <div className="flex items-center justify-end gap-2">
        {isDirty && (
          <Button variant="outline" onClick={discard}>
            Discard
          </Button>
        )}
        <Button onClick={apply} disabled={!isDirty}>
          Save
        </Button>
      </div>
    </div>
  )
}
