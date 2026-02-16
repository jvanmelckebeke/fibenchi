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
import { useSettings, type AppSettings, type MacdStyle } from "@/lib/settings"

function SettingSwitch({
  id,
  label,
  settingKey,
  draft,
  onChange,
}: {
  id: string
  label: string
  settingKey: keyof AppSettings
  draft: AppSettings
  onChange: (patch: Partial<AppSettings>) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <Label htmlFor={id}>{label}</Label>
      <Switch
        id={id}
        checked={draft[settingKey] as boolean}
        onCheckedChange={(v) => onChange({ [settingKey]: v })}
      />
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
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Watchlist Card Indicators</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingSwitch id="wl-sparkline" label="Sparkline Chart" settingKey="watchlist_show_sparkline" draft={draft} onChange={change} />
          <SettingSwitch id="wl-rsi" label="RSI Gauge" settingKey="watchlist_show_rsi" draft={draft} onChange={change} />
          <SettingSwitch id="wl-macd" label="MACD Indicator" settingKey="watchlist_show_macd" draft={draft} onChange={change} />
          {draft.watchlist_show_macd && (
            <div className="flex items-center justify-between pl-4">
              <Label className="text-muted-foreground">MACD Style</Label>
              <Select
                value={draft.watchlist_macd_style}
                onValueChange={(v) => change({ watchlist_macd_style: v as MacdStyle })}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="classic">Classic</SelectItem>
                  <SelectItem value="divergence">Divergence</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Detail Page Chart</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingSwitch id="dt-sma20" label="SMA 20" settingKey="detail_show_sma20" draft={draft} onChange={change} />
          <SettingSwitch id="dt-sma50" label="SMA 50" settingKey="detail_show_sma50" draft={draft} onChange={change} />
          <SettingSwitch id="dt-bb" label="Bollinger Bands" settingKey="detail_show_bollinger" draft={draft} onChange={change} />
          <SettingSwitch id="dt-rsi" label="RSI Chart" settingKey="detail_show_rsi_chart" draft={draft} onChange={change} />
          <SettingSwitch id="dt-macd" label="MACD Chart" settingKey="detail_show_macd_chart" draft={draft} onChange={change} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Chart Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
          <SettingSwitch id="compact" label="Compact Mode" settingKey="compact_mode" draft={draft} onChange={change} />
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
