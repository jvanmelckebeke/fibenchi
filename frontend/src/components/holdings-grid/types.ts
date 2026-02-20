import { getHoldingSummaryDescriptors } from "@/lib/indicator-registry"

export interface IndicatorData {
  currency: string
  close: number | null
  change_pct: number | null
  values: Record<string, number | string | null>
}

export interface HoldingsGridRow {
  key: string | number
  symbol: string
  name: string
  percent: number | null
}

export const SUMMARY_DESCRIPTORS = getHoldingSummaryDescriptors()
