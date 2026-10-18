import { Link } from "react-router-dom"

export function SymbolLegend({
  sortedSymbols,
  symbolColorMap,
  values,
  valueColors,
  suffix,
}: {
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
  values?: (string | undefined)[]
  valueColors?: (string | undefined)[]
  suffix?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1">
      {sortedSymbols.map((sym, idx) => (
        <div key={sym} className="flex items-center gap-1.5 text-xs">
          <div
            className="h-3 w-3 flex-shrink-0 rounded-sm"
            style={{ backgroundColor: symbolColorMap.get(sym) }}
          />
          <Link
            to={`/asset/${sym}`}
            className="text-muted-foreground hover:text-foreground hover:underline">
            {sym}
          </Link>
          {values?.[idx] !== undefined && (
            <span className={`font-mono ${valueColors?.[idx] ?? "text-muted-foreground"}`}>
              {values[idx]}
            </span>
          )}
        </div>
      ))}
      {suffix}
    </div>
  )
}
