// TypeScript types matching backend Pydantic schemas

export type AssetType = "stock" | "etf"

export interface TagBrief {
  id: number
  name: string
  color: string
}

export interface Tag {
  id: number
  name: string
  color: string
  created_at: string
  assets: Asset[]
}

export interface TagCreate {
  name: string
  color?: string
}

export interface TagUpdate {
  name?: string
  color?: string
}

export interface Asset {
  id: number
  symbol: string
  name: string
  type: AssetType
  currency: string
  created_at: string
  tags: TagBrief[]
}

export interface AssetCreate {
  symbol: string
  name?: string
  type?: AssetType
  add_to_watchlist?: boolean
}

export interface SymbolSearchResult {
  symbol: string
  name: string
  exchange: string
  type: AssetType
}

export interface Group {
  id: number
  name: string
  description: string | null
  is_default: boolean
  position: number
  created_at: string
  assets: Asset[]
}

export interface GroupCreate {
  name: string
  description?: string
}

export interface GroupUpdate {
  name?: string
  description?: string
}

export interface Price {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Indicator {
  date: string
  close: number
  rsi: number | null
  sma_20: number | null
  sma_50: number | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
}

export interface AssetDetail {
  prices: Price[]
  indicators: Indicator[]
}

export interface Annotation {
  id: number
  date: string
  title: string
  body: string | null
  color: string
  created_at: string
}

export interface AnnotationCreate {
  date: string
  title: string
  body?: string
  color?: string
}

export interface Thesis {
  content: string
  updated_at: string
}

export interface SyncResult {
  symbol: string
  synced: number
}

export interface Holding {
  symbol: string
  name: string
  percent: number
}

export interface SectorWeighting {
  sector: string
  percent: number
}

export interface EtfHoldings {
  top_holdings: Holding[]
  sector_weightings: SectorWeighting[]
  total_percent: number
}

export interface HoldingIndicator {
  symbol: string
  currency: string
  close: number | null
  change_pct: number | null
  rsi: number | null
  sma_20: number | null
  sma_50: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
  macd_signal_dir: string | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
  bb_position: string | null
}

export interface PortfolioIndex {
  dates: string[]
  values: number[]
  current: number
  change: number
  change_pct: number
}

export interface AssetPerformance {
  symbol: string
  name: string
  type: string
  change_pct: number
}

export interface PseudoETF {
  id: number
  name: string
  description: string | null
  base_date: string
  base_value: number
  created_at: string
  constituents: Asset[]
}

export interface PseudoETFCreate {
  name: string
  description?: string
  base_date: string
  base_value?: number
}

export interface PseudoETFUpdate {
  name?: string
  description?: string
  base_date?: string
}

export interface PerformancePoint {
  date: string
  value: number
}

export interface PerformanceBreakdownPoint {
  date: string
  value: number
  breakdown: Record<string, number>
}

export interface ConstituentIndicator {
  symbol: string
  name: string | null
  currency: string
  weight_pct: number | null
  close: number | null
  change_pct: number | null
  rsi: number | null
  sma_20: number | null
  sma_50: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
  macd_signal_dir: string | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
  bb_position: string | null
}

export interface SparklinePoint {
  date: string
  close: number
}

export interface IndicatorSummary {
  rsi: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
}

export interface Quote {
  symbol: string
  price: number | null
  previous_close: number | null
  change: number | null
  change_percent: number | null
  currency: string
  market_state: string | null
}
