import { Fragment } from "react"
import {
  getOverlayDescriptors,
  getDescriptorById,
  resolveThresholdColor,
  type IndicatorDescriptor,
  type SeriesDescriptor,
} from "@/lib/indicator-registry"

export interface LegendValues {
  o?: number
  h?: number
  l?: number
  c?: number
  indicators: Record<string, number | undefined>
}

function seriesTextColor(s: SeriesDescriptor): string {
  return s.legendColor || s.color
}

function OverlayEntry({ descriptor, v }: { descriptor: IndicatorDescriptor; v: LegendValues }) {
  const hasData = descriptor.series.some((s) => v.indicators[s.field] !== undefined)
  if (!hasData) return null

  if (descriptor.series.length === 1) {
    const s = descriptor.series[0]
    const val = v.indicators[s.field]
    const color = seriesTextColor(s)
    return (
      <span>
        <span className="inline-block w-2 h-0.5 mr-1 align-middle" style={{ backgroundColor: color }} />
        {s.label}{" "}
        <span style={{ color }}>{val?.toFixed(descriptor.decimals)}</span>
      </span>
    )
  }

  // Multi-series (e.g. Bollinger Bands) — show short label + all values
  const color = seriesTextColor(descriptor.series[0])
  return (
    <span style={{ color }}>
      {descriptor.shortLabel}{" "}
      {descriptor.series.map((s, i) => (
        <Fragment key={s.field}>
          {i > 0 && " / "}
          <span>{v.indicators[s.field]?.toFixed(descriptor.decimals)}</span>
        </Fragment>
      ))}
    </span>
  )
}

export function Legend({ values, latest }: { values: LegendValues | null; latest: LegendValues }) {
  const v = values ?? latest
  const changeColor = v.c !== undefined && v.o !== undefined
    ? v.c >= v.o ? "text-emerald-500" : "text-red-500"
    : ""

  const overlays = getOverlayDescriptors()

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs tabular-nums">
      {v.o !== undefined && v.h !== undefined && v.l !== undefined && v.c !== undefined && (
        <>
          <span className="text-muted-foreground">O <span className={changeColor}>{v.o.toFixed(2)}</span></span>
          <span className="text-muted-foreground">H <span className={changeColor}>{v.h.toFixed(2)}</span></span>
          <span className="text-muted-foreground">L <span className={changeColor}>{v.l.toFixed(2)}</span></span>
          <span className="text-muted-foreground">C <span className={changeColor}>{v.c.toFixed(2)}</span></span>
        </>
      )}
      {overlays.map((desc) => (
        <OverlayEntry key={desc.id} descriptor={desc} v={v} />
      ))}
    </div>
  )
}

export function SubChartLegend({ descriptorId, values, latest }: {
  descriptorId: string
  values: LegendValues | null
  latest: LegendValues
}) {
  const desc = getDescriptorById(descriptorId)
  if (!desc) return null

  const v = values ?? latest

  return (
    <div className="flex items-center gap-x-3 text-xs tabular-nums">
      <span className="text-muted-foreground">{desc.label}</span>
      {desc.series.map((s) => {
        const val = v.indicators[s.field]
        if (val === undefined) return null

        // Use threshold color (Tailwind class) if available, otherwise inline style
        const thresholdClass = resolveThresholdColor(s.thresholdColors, val)
        const color = seriesTextColor(s)

        if (thresholdClass) {
          return (
            <span key={s.field} className={thresholdClass}>
              {s.label} {val.toFixed(desc.decimals)}
            </span>
          )
        }

        return (
          <span key={s.field}>
            <span className="inline-block w-2 h-0.5 mr-1 align-middle" style={{ backgroundColor: color }} />
            {s.label}{" "}
            <span style={{ color }}>{val.toFixed(desc.decimals)}</span>
          </span>
        )
      })}
    </div>
  )
}
