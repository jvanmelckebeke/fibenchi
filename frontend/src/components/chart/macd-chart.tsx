import type { IChartApi } from "lightweight-charts"
import { SubChart } from "./sub-chart"

interface MacdChartProps {
  showLegend?: boolean
  roundedClass?: string
  onChartReady?: (chart: IChartApi) => void
  onChartDestroy?: () => void
}

export function MacdChart(props: MacdChartProps) {
  return <SubChart descriptorId="macd" {...props} />
}
