export interface LegendValues {
  o?: number
  h?: number
  l?: number
  c?: number
  sma20?: number
  sma50?: number
  bbUpper?: number
  bbLower?: number
  rsi?: number
}

export function Legend({ values, latest }: { values: LegendValues | null; latest: LegendValues }) {
  const v = values ?? latest
  const changeColor = v.c !== undefined && v.o !== undefined
    ? v.c >= v.o ? "text-green-500" : "text-red-500"
    : ""

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs tabular-nums">
      {v.o !== undefined && (
        <>
          <span className="text-muted-foreground">O <span className={changeColor}>{v.o.toFixed(2)}</span></span>
          <span className="text-muted-foreground">H <span className={changeColor}>{v.h!.toFixed(2)}</span></span>
          <span className="text-muted-foreground">L <span className={changeColor}>{v.l!.toFixed(2)}</span></span>
          <span className="text-muted-foreground">C <span className={changeColor}>{v.c!.toFixed(2)}</span></span>
        </>
      )}
      {v.sma20 !== undefined && (
        <span><span className="inline-block w-2 h-0.5 bg-teal-500 mr-1 align-middle" />SMA 20 <span className="text-teal-500">{v.sma20.toFixed(2)}</span></span>
      )}
      {v.sma50 !== undefined && (
        <span><span className="inline-block w-2 h-0.5 bg-violet-500 mr-1 align-middle" />SMA 50 <span className="text-violet-500">{v.sma50.toFixed(2)}</span></span>
      )}
      {v.bbUpper !== undefined && v.bbLower !== undefined && (
        <span className="text-blue-400">BB <span>{v.bbUpper.toFixed(2)}</span> / <span>{v.bbLower.toFixed(2)}</span></span>
      )}
    </div>
  )
}

export function RsiLegend({ values, latest }: { values: LegendValues | null; latest: LegendValues }) {
  const rsi = (values ?? latest).rsi
  const color = rsi !== undefined
    ? rsi >= 70 ? "text-red-500" : rsi <= 30 ? "text-green-500" : "text-violet-500"
    : "text-muted-foreground"

  return (
    <div className="text-xs tabular-nums">
      <span className="text-muted-foreground">RSI(14) </span>
      {rsi !== undefined && <span className={color}>{rsi.toFixed(2)}</span>}
    </div>
  )
}
