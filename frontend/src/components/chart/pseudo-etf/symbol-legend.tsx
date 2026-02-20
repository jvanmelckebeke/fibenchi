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
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 items-center">
      {sortedSymbols.map((sym, idx) => (
        <div key={sym} className="flex items-center gap-1.5 text-xs">
          <div
            className="w-3 h-3 rounded-sm flex-shrink-0"
            style={{ backgroundColor: symbolColorMap.get(sym) }}
          />
          <Link to={`/asset/${sym}`} className="hover:underline text-muted-foreground hover:text-foreground">
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
