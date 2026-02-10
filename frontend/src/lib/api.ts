// TypeScript types matching backend Pydantic schemas

export type AssetType = "stock" | "etf"

export interface Asset {
  id: number
  symbol: string
  name: string
  type: AssetType
  created_at: string
}

export interface AssetCreate {
  symbol: string
  name?: string
  type?: AssetType
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

// Assets
export const api = {
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
    refresh: (symbol: string) =>
      request<SyncResult>(`/assets/${symbol}/refresh`, { method: "POST" }),
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
}
