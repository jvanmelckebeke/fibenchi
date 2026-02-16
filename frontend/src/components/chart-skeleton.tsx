export function ChartSkeleton({ height = 520 }: { height?: number }) {
  return (
    <div
      className="rounded-lg border border-border bg-card overflow-hidden"
      style={{ height }}
    >
      <svg
        viewBox="0 0 800 400"
        preserveAspectRatio="none"
        className="h-full w-full text-muted-foreground/10"
      >
        {/* Y-axis ticks */}
        {[80, 160, 240, 320].map((y) => (
          <line key={y} x1={60} y1={y} x2={780} y2={y} stroke="currentColor" strokeWidth={1} />
        ))}
        {/* X-axis */}
        <line x1={60} y1={360} x2={780} y2={360} stroke="currentColor" strokeWidth={1} />
        {/* Fake candle bars */}
        <g className="animate-pulse">
          {Array.from({ length: 24 }, (_, i) => {
            const x = 80 + i * 30
            const h = 40 + Math.abs(Math.sin(i * 0.7)) * 80
            const y = 180 + Math.sin(i * 0.5) * 60 - h / 2
            return (
              <rect
                key={i}
                x={x}
                y={y}
                width={12}
                height={h}
                rx={2}
                className="fill-muted-foreground/15"
              />
            )
          })}
        </g>
      </svg>
    </div>
  )
}
