export function IndicatorCell({ value, className = "" }: { value: string | null; className?: string }) {
  return (
    <span className={`text-right text-xs ${value === null ? "text-muted-foreground" : className}`}>
      {value ?? "\u2014"}
    </span>
  )
}
