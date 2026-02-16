import { Button } from "@/components/ui/button"

const DEFAULT_PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

interface PeriodSelectorProps {
  value: string
  onChange: (period: string) => void
  periods?: readonly string[]
}

export function PeriodSelector({
  value,
  onChange,
  periods = DEFAULT_PERIODS,
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
