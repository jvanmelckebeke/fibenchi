import type {
  Annotation,
  AnnotationCreate,
  Asset,
  AssetCreate,
  AssetDetail,
  AssetPerformance,
  ConstituentIndicator,
  EtfHoldings,
  Group,
  GroupCreate,
  GroupUpdate,
  HoldingIndicator,
  IndicatorSummary,
  PerformanceBreakdownPoint,
  PortfolioIndex,
  ProviderInfo,
  PseudoETF,
  PseudoETFCreate,
  PseudoETFUpdate,
  SparklinePoint,
  SymbolSearchResult,
  SymbolSource,
  SymbolSourceCreate,
  SymbolSourceUpdate,
  SyncResult,
  Tag,
  TagBrief,
  TagCreate,
  Thesis,
} from "./types"

export type * from "./types"

// API client

const BASE = "/api"

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string] => entry[1] !== undefined,
  )
  return entries.length ? `?${new URLSearchParams(entries)}` : ""
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
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
      request<PortfolioIndex>(`/portfolio/index${qs({ period })}`),
    performers: (period?: string) =>
      request<AssetPerformance[]>(`/portfolio/performers${qs({ period })}`),
  },
  assets: {
    list: () => request<Asset[]>("/assets"),
    create: (data: AssetCreate) =>
      request<Asset>("/assets", { method: "POST", body: JSON.stringify(data) }),
  },
  prices: {
    detail: (symbol: string, period?: string) =>
      request<AssetDetail>(`/assets/${symbol}/detail${qs({ period })}`),
    refresh: (symbol: string, period?: string) =>
      request<SyncResult>(`/assets/${symbol}/refresh${qs({ period })}`, { method: "POST" }),
    holdings: (symbol: string) =>
      request<EtfHoldings>(`/assets/${symbol}/holdings`),
    holdingsIndicators: (symbol: string) =>
      request<HoldingIndicator[]>(`/assets/${symbol}/holdings/indicators`),
  },
  tags: {
    list: () => request<Tag[]>("/tags"),
    create: (data: TagCreate) =>
      request<Tag>("/tags", { method: "POST", body: JSON.stringify(data) }),
    attach: (symbol: string, tagId: number) =>
      request<TagBrief[]>(`/assets/${symbol}/tags/${tagId}`, { method: "POST" }),
    detach: (symbol: string, tagId: number) =>
      request<TagBrief[]>(`/assets/${symbol}/tags/${tagId}`, { method: "DELETE" }),
  },
  groups: {
    list: () => request<Group[]>("/groups"),
    get: (id: number) => request<Group>(`/groups/${id}`),
    create: (data: GroupCreate) =>
      request<Group>("/groups", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: GroupUpdate) =>
      request<Group>(`/groups/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<void>(`/groups/${id}`, { method: "DELETE" }),
    reorder: (groupIds: number[]) =>
      request<Group[]>("/groups/reorder", { method: "PUT", body: JSON.stringify({ group_ids: groupIds }) }),
    addAssets: (id: number, assetIds: number[]) =>
      request<Group>(`/groups/${id}/assets`, {
        method: "POST",
        body: JSON.stringify({ asset_ids: assetIds }),
      }),
    removeAsset: (groupId: number, assetId: number) =>
      request<Group>(`/groups/${groupId}/assets/${assetId}`, { method: "DELETE" }),
    sparklines: (id: number, period?: string) =>
      request<Record<string, SparklinePoint[]>>(`/groups/${id}/sparklines${qs({ period })}`),
    indicators: (id: number) =>
      request<Record<string, IndicatorSummary>>(`/groups/${id}/indicators`),
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
  search: (q: string) => request<SymbolSearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
  searchLocal: (q: string) => request<SymbolSearchResult[]>(`/search?q=${encodeURIComponent(q)}&source=local`),
  searchYahoo: (q: string) => request<SymbolSearchResult[]>(`/search?q=${encodeURIComponent(q)}&source=yahoo`),
  settings: {
    get: () => request<{ data: Record<string, unknown> }>("/settings"),
    update: (data: Record<string, unknown>) =>
      request<{ data: Record<string, unknown> }>("/settings", {
        method: "PUT",
        body: JSON.stringify({ data }),
      }),
  },
  symbolSources: {
    list: () => request<SymbolSource[]>("/symbol-sources"),
    providers: () => request<Record<string, ProviderInfo>>("/symbol-sources/providers"),
    create: (data: SymbolSourceCreate) =>
      request<SymbolSource>("/symbol-sources", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: SymbolSourceUpdate) =>
      request<SymbolSource>(`/symbol-sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    sync: (id: number) =>
      request<{ source_id: number; symbols_synced: number; message: string }>(
        `/symbol-sources/${id}/sync`, { method: "POST" },
      ),
    delete: (id: number) =>
      request<void>(`/symbol-sources/${id}`, { method: "DELETE" }),
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
