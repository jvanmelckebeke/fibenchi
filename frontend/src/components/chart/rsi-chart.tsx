import type { IChartApi } from "lightweight-charts"
import { SubChart } from "./sub-chart"

interface RsiChartProps {
  showLegend?: boolean
  roundedClass?: string
  onChartReady?: (chart: IChartApi) => void
  onChartDestroy?: () => void
}

export function RsiChart(props: RsiChartProps) {
  return <SubChart descriptorId="rsi" {...props} />
}
