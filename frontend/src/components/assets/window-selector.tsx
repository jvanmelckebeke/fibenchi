import { useState } from "react"
import { CalendarDays } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { STANDARD_PERIODS, relativeStart, ytdStart, todayISO, type AssetWindow } from "@/lib/asset-window"
import { formatDateShort } from "@/lib/format"

const RELATIVE_PRESETS: { label: string; days: number }[] = [
  { label: "1W", days: 7 },
  { label: "2W", days: 14 },
  { label: "3W", days: 21 },
]

interface WindowSelectorProps {
  value: AssetWindow
  onChange: (window: AssetWindow) => void
}

export function WindowSelector({ value, onChange }: WindowSelectorProps) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(value.kind === "since" ? value.start : "")
  const isCustom = value.kind === "since"

  const applySince = (start: string) => {
    if (!start) return
    onChange({ kind: "since", start })
    setOpen(false)
  }

  return (
    <div className="flex gap-1">
      {STANDARD_PERIODS.map((p) => (
        <Button
          key={p}
          variant={value.kind === "period" && value.period === p ? "default" : "ghost"}
          size="sm"
          onClick={() => onChange({ kind: "period", period: p })}
          className="text-xs"
        >
          {p}
        </Button>
      ))}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant={isCustom ? "default" : "ghost"} size="sm" className="text-xs gap-1.5">
            <CalendarDays className="h-3.5 w-3.5" />
            {isCustom ? formatDateShort(value.start) : "Custom"}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-56 space-y-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1.5">Recent</p>
            <div className="flex flex-wrap gap-1">
              {RELATIVE_PRESETS.map((r) => (
                <Button
                  key={r.label}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => applySince(relativeStart(r.days))}
                >
                  {r.label}
                </Button>
              ))}
              <Button variant="outline" size="sm" className="text-xs" onClick={() => applySince(ytdStart())}>
                YTD
              </Button>
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1.5">Since a date</p>
            <div className="flex gap-1.5">
              <Input
                type="date"
                max={todayISO()}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="h-8 text-xs"
              />
              <Button size="sm" className="text-xs" disabled={!draft} onClick={() => applySince(draft)}>
                Apply
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
