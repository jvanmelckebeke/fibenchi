import type {
  IChartApi,
  ISeriesApi,
  SeriesType,
  Time,
} from "lightweight-charts"

export interface BandPoint {
  time: string
  upper: number
  lower: number
}

class BandFillRenderer {
  private _source: BandFillPrimitive

  constructor(source: BandFillPrimitive) {
    this._source = source
  }

  draw() {
    // intentionally empty — all drawing is in drawBackground
  }

  drawBackground(target: { useMediaCoordinateSpace: <T>(fn: (scope: { context: CanvasRenderingContext2D }) => T) => T }) {
    const { chart, series, data } = this._source
    if (!chart || !series || !data.length) return

    const timeScale = chart.timeScale()
    target.useMediaCoordinateSpace(({ context: ctx }) => {
      const upper: Array<{ x: number; y: number }> = []
      const lower: Array<{ x: number; y: number }> = []

      for (const d of data) {
        const x = timeScale.timeToCoordinate(d.time as unknown as Time)
        const yU = series.priceToCoordinate(d.upper)
        const yL = series.priceToCoordinate(d.lower)
        if (x === null || yU === null || yL === null) continue
        upper.push({ x, y: yU })
        lower.push({ x, y: yL })
      }

      if (upper.length < 2) return

      ctx.beginPath()
      ctx.moveTo(upper[0].x, upper[0].y)
      for (let i = 1; i < upper.length; i++) ctx.lineTo(upper[i].x, upper[i].y)
      for (let i = lower.length - 1; i >= 0; i--) ctx.lineTo(lower[i].x, lower[i].y)
      ctx.closePath()
      ctx.fillStyle = "rgba(96, 165, 250, 0.18)"
      ctx.fill()
    })
  }
}

class BandFillPaneView {
  private _renderer: BandFillRenderer

  constructor(source: BandFillPrimitive) {
    this._renderer = new BandFillRenderer(source)
  }

  zOrder() {
    return "bottom" as const
  }

  renderer() {
    return this._renderer
  }
}

export class BandFillPrimitive {
  data: BandPoint[]
  chart: IChartApi | null = null
  series: ISeriesApi<SeriesType> | null = null
  private _views: readonly [BandFillPaneView]

  constructor(data: BandPoint[]) {
    this.data = data
    this._views = [new BandFillPaneView(this)]
  }

  attached({ chart, series }: { chart: IChartApi; series: ISeriesApi<SeriesType> }) {
    this.chart = chart
    this.series = series
  }

  detached() {
    this.chart = null
    this.series = null
  }

  paneViews() {
    return this._views
  }
}
