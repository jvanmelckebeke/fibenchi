import type { PerformanceBreakdownPoint } from "@/lib/api"

/** Shared inputs for the pseudo-ETF breakdown charts (overlay + daily contribution). */
export interface BreakdownChartProps {
  data: PerformanceBreakdownPoint[]
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
}
