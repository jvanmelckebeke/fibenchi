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
  watchlisted: boolean
  currency: string
  created_at: string
  tags: TagBrief[]
}

export interface AssetCreate {
  symbol: string
  name?: string
  type?: AssetType
  watchlisted?: boolean
}

export interface Group {
  id: number
  name: string
  description: string | null
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

// API client

const BASE = "/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Portfolio & Assets
export const api = {
  portfolio: {
    index: (period?: string) =>
      request<PortfolioIndex>(`/portfolio/index${period ? `?period=${period}` : ""}`),
    performers: (period?: string) =>
      request<AssetPerformance[]>(`/portfolio/performers${period ? `?period=${period}` : ""}`),
  },
  assets: {
    list: () => request<Asset[]>("/assets"),
    create: (data: AssetCreate) =>
      request<Asset>("/assets", { method: "POST", body: JSON.stringify(data) }),
    delete: (symbol: string) =>
      request<void>(`/assets/${symbol}`, { method: "DELETE" }),
  },
  prices: {
    list: (symbol: string, period?: string) =>
      request<Price[]>(`/assets/${symbol}/prices${period ? `?period=${period}` : ""}`),
    indicators: (symbol: string, period?: string) =>
      request<Indicator[]>(`/assets/${symbol}/indicators${period ? `?period=${period}` : ""}`),
    refresh: (symbol: string, period?: string) =>
      request<SyncResult>(`/assets/${symbol}/refresh${period ? `?period=${period}` : ""}`, { method: "POST" }),
    holdings: (symbol: string) =>
      request<EtfHoldings>(`/assets/${symbol}/holdings`),
    holdingsIndicators: (symbol: string) =>
      request<HoldingIndicator[]>(`/assets/${symbol}/holdings/indicators`),
  },
  tags: {
    list: () => request<Tag[]>("/tags"),
    create: (data: TagCreate) =>
      request<Tag>("/tags", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: TagUpdate) =>
      request<Tag>(`/tags/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<void>(`/tags/${id}`, { method: "DELETE" }),
    attach: (symbol: string, tagId: number) =>
      request<TagBrief[]>(`/assets/${symbol}/tags/${tagId}`, { method: "POST" }),
    detach: (symbol: string, tagId: number) =>
      request<TagBrief[]>(`/assets/${symbol}/tags/${tagId}`, { method: "DELETE" }),
  },
  groups: {
    list: () => request<Group[]>("/groups"),
    create: (data: GroupCreate) =>
      request<Group>("/groups", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: GroupUpdate) =>
      request<Group>(`/groups/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<void>(`/groups/${id}`, { method: "DELETE" }),
    addAssets: (id: number, assetIds: number[]) =>
      request<Group>(`/groups/${id}/assets`, {
        method: "POST",
        body: JSON.stringify({ asset_ids: assetIds }),
      }),
    removeAsset: (groupId: number, assetId: number) =>
      request<Group>(`/groups/${groupId}/assets/${assetId}`, { method: "DELETE" }),
  },
  thesis: {
    get: (symbol: string) => request<Thesis>(`/assets/${symbol}/thesis`),
    update: (symbol: string, content: string) =>
      request<Thesis>(`/assets/${symbol}/thesis`, {
        method: "PUT",
        body: JSON.stringify({ content }),
      }),
  },
  annotations: {
    list: (symbol: string) => request<Annotation[]>(`/assets/${symbol}/annotations`),
    create: (symbol: string, data: AnnotationCreate) =>
      request<Annotation>(`/assets/${symbol}/annotations`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (symbol: string, id: number) =>
      request<void>(`/assets/${symbol}/annotations/${id}`, { method: "DELETE" }),
  },
  watchlist: {
    sparklines: (period?: string) =>
      request<Record<string, SparklinePoint[]>>(`/watchlist/sparklines${period ? `?period=${period}` : ""}`),
    indicators: () =>
      request<Record<string, IndicatorSummary>>("/watchlist/indicators"),
  },
  settings: {
    get: () => request<{ data: Record<string, unknown> }>("/settings"),
    update: (data: Record<string, unknown>) =>
      request<{ data: Record<string, unknown> }>("/settings", {
        method: "PUT",
        body: JSON.stringify({ data }),
      }),
  },
  pseudoEtfs: {
    list: () => request<PseudoETF[]>("/pseudo-etfs"),
    create: (data: PseudoETFCreate) =>
      request<PseudoETF>("/pseudo-etfs", { method: "POST", body: JSON.stringify(data) }),
    get: (id: number) => request<PseudoETF>(`/pseudo-etfs/${id}`),
    update: (id: number, data: PseudoETFUpdate) =>
      request<PseudoETF>(`/pseudo-etfs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<void>(`/pseudo-etfs/${id}`, { method: "DELETE" }),
    addConstituents: (id: number, assetIds: number[]) =>
      request<PseudoETF>(`/pseudo-etfs/${id}/constituents`, {
        method: "POST",
        body: JSON.stringify({ asset_ids: assetIds }),
      }),
    removeConstituent: (etfId: number, assetId: number) =>
      request<PseudoETF>(`/pseudo-etfs/${etfId}/constituents/${assetId}`, { method: "DELETE" }),
    performance: (id: number) => request<PerformanceBreakdownPoint[]>(`/pseudo-etfs/${id}/performance`),
    constituentsIndicators: (id: number) => request<ConstituentIndicator[]>(`/pseudo-etfs/${id}/constituents/indicators`),
    thesis: {
      get: (id: number) => request<Thesis>(`/pseudo-etfs/${id}/thesis`),
      update: (id: number, content: string) =>
        request<Thesis>(`/pseudo-etfs/${id}/thesis`, {
          method: "PUT",
          body: JSON.stringify({ content }),
        }),
    },
    annotations: {
      list: (id: number) => request<Annotation[]>(`/pseudo-etfs/${id}/annotations`),
      create: (id: number, data: AnnotationCreate) =>
        request<Annotation>(`/pseudo-etfs/${id}/annotations`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      delete: (id: number, annotationId: number) =>
        request<void>(`/pseudo-etfs/${id}/annotations/${annotationId}`, { method: "DELETE" }),
    },
  },
}
