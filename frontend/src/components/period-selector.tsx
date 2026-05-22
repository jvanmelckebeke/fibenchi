import { Button } from "@/components/ui/button"
import { STANDARD_PERIODS } from "@/lib/asset-window"

interface PeriodSelectorProps {
  value: string
  onChange: (period: string) => void
  periods?: readonly string[]
}

export function PeriodSelector({
  value,
  onChange,
  periods = STANDARD_PERIODS,
}: PeriodSelectorProps) {
  return (
    <div className="flex gap-1">
      {periods.map((p) => (
        <Button
          key={p}
          variant={value === p ? "default" : "ghost"}
          size="sm"
          onClick={() => onChange(p)}
          className="text-xs"
        >
          {p}
        </Button>
      ))}
    </div>
  )
}
