import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import { useCallback } from "react"
import { api, type Asset, type AssetCreate, type Group, type GroupCreate, type GroupUpdate, type TagCreate, type AnnotationCreate, type PseudoETFCreate, type PseudoETFUpdate, type SymbolSearchResult, type SymbolSourceCreate, type SymbolSourceUpdate } from "./api"

const STALE_5MIN = 5 * 60_000
const STALE_24H = 24 * 60 * 60_000

function useInvalidatingMutation<TData, TVariables>(
  mutationFn: (vars: TVariables) => Promise<TData>,
  invalidateKeys: readonly (readonly unknown[])[],
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      for (const key of invalidateKeys) {
        qc.invalidateQueries({ queryKey: key })
      }
    },
  })
}

// Keys
export const keys = {
  portfolioIndex: (period?: string) => ["portfolio-index", period] as const,
  portfolioPerformers: (period?: string) => ["portfolio-performers", period] as const,
  assets: ["assets"] as const,
  assetDetail: (symbol: string, period?: string) => ["asset-detail", symbol, period] as const,
  etfHoldings: (symbol: string) => ["etf-holdings", symbol] as const,
  holdingsIndicators: (symbol: string) => ["holdings-indicators", symbol] as const,
  tags: ["tags"] as const,
  groups: ["groups"] as const,
  group: (id: number) => ["groups", id] as const,
  groupSparklines: (id: number, period?: string) => ["group-sparklines", id, period] as const,
  groupIndicators: (id: number) => ["group-indicators", id] as const,
  thesis: (symbol: string) => ["thesis", symbol] as const,
  annotations: (symbol: string) => ["annotations", symbol] as const,
  pseudoEtfs: ["pseudo-etfs"] as const,
  pseudoEtf: (id: number) => ["pseudo-etfs", id] as const,
  pseudoEtfPerformance: (id: number) => ["pseudo-etfs", id, "performance"] as const,
  pseudoEtfConstituentsIndicators: (id: number) => ["pseudo-etfs", id, "constituents-indicators"] as const,
  pseudoEtfThesis: (id: number) => ["pseudo-etfs", id, "thesis"] as const,
  pseudoEtfAnnotations: (id: number) => ["pseudo-etfs", id, "annotations"] as const,
  symbolSearchLocal: (q: string) => ["symbol-search-local", q] as const,
  symbolSearchYahoo: (q: string) => ["symbol-search-yahoo", q] as const,
  symbolSources: ["symbol-sources"] as const,
  symbolSourceProviders: ["symbol-source-providers"] as const,
}

// Portfolio
export function usePortfolioIndex(period?: string) {
  return useQuery({
    queryKey: keys.portfolioIndex(period),
    queryFn: () => api.portfolio.index(period),
    staleTime: STALE_5MIN,
    placeholderData: keepPreviousData,
  })
}

export function usePortfolioPerformers(period?: string) {
  return useQuery({
    queryKey: keys.portfolioPerformers(period),
    queryFn: () => api.portfolio.performers(period),
    staleTime: STALE_5MIN,
    placeholderData: keepPreviousData,
  })
}

// Assets
export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: api.assets.list, staleTime: STALE_5MIN })
}

export function useCreateAsset() {
  return useInvalidatingMutation(
    (data: AssetCreate) => api.assets.create(data),
    [keys.assets, keys.groups],
  )
}

// Search
export function useLocalSearch(query: string) {
  return useQuery<SymbolSearchResult[]>({
    queryKey: keys.symbolSearchLocal(query),
    queryFn: () => api.searchLocal(query),
    enabled: query.length >= 1,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  })
}

export function useYahooSearch(query: string) {
  return useQuery<SymbolSearchResult[]>({
    queryKey: keys.symbolSearchYahoo(query),
    queryFn: () => api.searchYahoo(query),
    enabled: query.length >= 1,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  })
}

// Prices & Indicators
export function useAssetDetail(symbol: string, period?: string, opts?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.assetDetail(symbol, period),
    queryFn: () => api.prices.detail(symbol, period),
    enabled: (opts?.enabled ?? true) && !!symbol,
    staleTime: STALE_5MIN, // 5 min — daily OHLCV data, SSE handles live quotes
    placeholderData: keepPreviousData,
  })
}

export function useEtfHoldings(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.etfHoldings(symbol),
    queryFn: () => api.prices.holdings(symbol),
    enabled: !!symbol && enabled,
    staleTime: STALE_24H, // cache 24h — holdings don't change often
  })
}

export function useHoldingsIndicators(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.holdingsIndicators(symbol),
    queryFn: () => api.prices.holdingsIndicators(symbol),
    enabled: !!symbol && enabled,
    staleTime: STALE_5MIN, // cache 5 min
  })
}

export function useRefreshPrices(symbol: string) {
  return useInvalidatingMutation(
    (period?: string) => api.prices.refresh(symbol, period),
    [["asset-detail", symbol]],
  )
}


// Prefetch — fire on hover to warm cache before navigation
export function usePrefetchAssetDetail(period: string) {
  const qc = useQueryClient()
  return useCallback(
    (symbol: string) =>
      qc.prefetchQuery({
        queryKey: keys.assetDetail(symbol, period),
        queryFn: () => api.prices.detail(symbol, period),
        staleTime: STALE_5MIN,
      }),
    [qc, period],
  )
}

// Tags
export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: api.tags.list, staleTime: STALE_5MIN })
}

export function useCreateTag() {
  return useInvalidatingMutation(
    (data: TagCreate) => api.tags.create(data),
    [keys.tags],
  )
}

export function useAttachTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ symbol, tagId }: { symbol: string; tagId: number }) =>
      api.tags.attach(symbol, tagId),
    onMutate: async ({ symbol, tagId }) => {
      await qc.cancelQueries({ queryKey: keys.assets })
      const previous = qc.getQueryData<Asset[]>(keys.assets)
      const tags = qc.getQueryData<{ id: number; name: string; color: string }[]>(keys.tags)
      const tag = tags?.find((t) => t.id === tagId)
      if (tag) {
        qc.setQueryData<Asset[]>(keys.assets, (old) =>
          old?.map((a) =>
            a.symbol === symbol && !a.tags.some((t) => t.id === tagId)
              ? { ...a, tags: [...a.tags, { id: tag.id, name: tag.name, color: tag.color }] }
              : a,
          ),
        )
      }
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(keys.assets, context.previous)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.assets })
      qc.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

export function useDetachTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ symbol, tagId }: { symbol: string; tagId: number }) =>
      api.tags.detach(symbol, tagId),
    onMutate: async ({ symbol, tagId }) => {
      await qc.cancelQueries({ queryKey: keys.assets })
      const previous = qc.getQueryData<Asset[]>(keys.assets)
      qc.setQueryData<Asset[]>(keys.assets, (old) =>
        old?.map((a) =>
          a.symbol === symbol
            ? { ...a, tags: a.tags.filter((t) => t.id !== tagId) }
            : a,
        ),
      )
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(keys.assets, context.previous)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.assets })
      qc.invalidateQueries({ queryKey: keys.tags })
    },
  })
}

// Groups
export function useGroups() {
  return useQuery({ queryKey: keys.groups, queryFn: api.groups.list, staleTime: STALE_5MIN })
}

export function useCreateGroup() {
  return useInvalidatingMutation(
    (data: GroupCreate) => api.groups.create(data),
    [keys.groups],
  )
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: GroupUpdate }) => api.groups.update(id, data),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.groups })
      qc.invalidateQueries({ queryKey: keys.group(vars.id) })
    },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.groups.delete(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.groups })
      qc.invalidateQueries({ queryKey: keys.group(id) })
    },
  })
}

export function useReorderGroups() {
  return useInvalidatingMutation(
    (groupIds: number[]) => api.groups.reorder(groupIds),
    [keys.groups],
  )
}

export function useAddAssetsToGroup() {
  return useInvalidatingMutation(
    ({ groupId, assetIds }: { groupId: number; assetIds: number[] }) =>
      api.groups.addAssets(groupId, assetIds),
    [keys.groups, keys.assets],
  )
}

export function useRemoveAssetFromGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, assetId }: { groupId: number; assetId: number }) =>
      api.groups.removeAsset(groupId, assetId),
    onMutate: async ({ groupId, assetId }) => {
      await qc.cancelQueries({ queryKey: keys.group(groupId) })
      const previous = qc.getQueryData<Group>(keys.group(groupId))
      qc.setQueryData<Group>(keys.group(groupId), (old) =>
        old ? { ...old, assets: old.assets.filter((a) => a.id !== assetId) } : old,
      )
      return { previous, groupId }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(keys.group(context.groupId), context.previous)
    },
    onSettled: (_data, _err, vars) => {
      qc.invalidateQueries({ queryKey: keys.groups })
      qc.invalidateQueries({ queryKey: keys.group(vars.groupId) })
    },
  })
}

export function useGroup(id: number) {
  return useQuery({
    queryKey: keys.group(id),
    queryFn: () => api.groups.get(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useGroupSparklines(id: number, period?: string) {
  return useQuery({
    queryKey: keys.groupSparklines(id, period),
    queryFn: () => api.groups.sparklines(id, period),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useGroupIndicators(id: number) {
  return useQuery({
    queryKey: keys.groupIndicators(id),
    queryFn: () => api.groups.indicators(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

// Thesis
export function useThesis(symbol: string) {
  return useQuery({
    queryKey: keys.thesis(symbol),
    queryFn: () => api.thesis.get(symbol),
    enabled: !!symbol,
    staleTime: STALE_5MIN,
  })
}

export function useUpdateThesis(symbol: string) {
  return useInvalidatingMutation(
    (content: string) => api.thesis.update(symbol, content),
    [keys.thesis(symbol)],
  )
}

// Annotations
export function useAnnotations(symbol: string) {
  return useQuery({
    queryKey: keys.annotations(symbol),
    queryFn: () => api.annotations.list(symbol),
    enabled: !!symbol,
    staleTime: STALE_5MIN,
  })
}

export function useCreateAnnotation(symbol: string) {
  return useInvalidatingMutation(
    (data: AnnotationCreate) => api.annotations.create(symbol, data),
    [keys.annotations(symbol)],
  )
}

export function useDeleteAnnotation(symbol: string) {
  return useInvalidatingMutation(
    (id: number) => api.annotations.delete(symbol, id),
    [keys.annotations(symbol)],
  )
}

// Pseudo-ETFs
export function usePseudoEtfs() {
  return useQuery({ queryKey: keys.pseudoEtfs, queryFn: api.pseudoEtfs.list, staleTime: STALE_5MIN })
}

export function usePseudoEtf(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtf(id),
    queryFn: () => api.pseudoEtfs.get(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useCreatePseudoEtf() {
  return useInvalidatingMutation(
    (data: PseudoETFCreate) => api.pseudoEtfs.create(data),
    [keys.pseudoEtfs],
  )
}

export function useUpdatePseudoEtf() {
  return useInvalidatingMutation(
    ({ id, data }: { id: number; data: PseudoETFUpdate }) => api.pseudoEtfs.update(id, data),
    [keys.pseudoEtfs],
  )
}

export function useDeletePseudoEtf() {
  return useInvalidatingMutation(
    (id: number) => api.pseudoEtfs.delete(id),
    [keys.pseudoEtfs],
  )
}

export function useAddPseudoEtfConstituents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ etfId, assetIds }: { etfId: number; assetIds: number[] }) =>
      api.pseudoEtfs.addConstituents(etfId, assetIds),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.pseudoEtfs })
      qc.invalidateQueries({ queryKey: keys.pseudoEtfPerformance(vars.etfId) })
      qc.invalidateQueries({ queryKey: keys.pseudoEtfConstituentsIndicators(vars.etfId) })
    },
  })
}

export function useRemovePseudoEtfConstituent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ etfId, assetId }: { etfId: number; assetId: number }) =>
      api.pseudoEtfs.removeConstituent(etfId, assetId),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.pseudoEtfs })
      qc.invalidateQueries({ queryKey: keys.pseudoEtfPerformance(vars.etfId) })
      qc.invalidateQueries({ queryKey: keys.pseudoEtfConstituentsIndicators(vars.etfId) })
    },
  })
}

export function usePseudoEtfPerformance(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtfPerformance(id),
    queryFn: () => api.pseudoEtfs.performance(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function usePseudoEtfConstituentsIndicators(id: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.pseudoEtfConstituentsIndicators(id),
    queryFn: () => api.pseudoEtfs.constituentsIndicators(id),
    enabled: !!id && enabled,
    staleTime: STALE_5MIN,
  })
}

// Pseudo-ETF Thesis
export function usePseudoEtfThesis(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtfThesis(id),
    queryFn: () => api.pseudoEtfs.thesis.get(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useUpdatePseudoEtfThesis(id: number) {
  return useInvalidatingMutation(
    (content: string) => api.pseudoEtfs.thesis.update(id, content),
    [keys.pseudoEtfThesis(id)],
  )
}

// Pseudo-ETF Annotations
export function usePseudoEtfAnnotations(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtfAnnotations(id),
    queryFn: () => api.pseudoEtfs.annotations.list(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useCreatePseudoEtfAnnotation(id: number) {
  return useInvalidatingMutation(
    (data: AnnotationCreate) => api.pseudoEtfs.annotations.create(id, data),
    [keys.pseudoEtfAnnotations(id)],
  )
}

export function useDeletePseudoEtfAnnotation(id: number) {
  return useInvalidatingMutation(
    (annotationId: number) => api.pseudoEtfs.annotations.delete(id, annotationId),
    [keys.pseudoEtfAnnotations(id)],
  )
}

// Symbol Sources
export function useSymbolSources() {
  return useQuery({ queryKey: keys.symbolSources, queryFn: api.symbolSources.list, staleTime: STALE_5MIN })
}

export function useSymbolSourceProviders() {
  return useQuery({ queryKey: keys.symbolSourceProviders, queryFn: api.symbolSources.providers, staleTime: STALE_24H })
}

export function useCreateSymbolSource() {
  return useInvalidatingMutation(
    (data: SymbolSourceCreate) => api.symbolSources.create(data),
    [keys.symbolSources],
  )
}

export function useUpdateSymbolSource() {
  return useInvalidatingMutation(
    ({ id, data }: { id: number; data: SymbolSourceUpdate }) => api.symbolSources.update(id, data),
    [keys.symbolSources],
  )
}

export function useSyncSymbolSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.symbolSources.sync(id),
    onSuccess: () => {
      // Refetch sources after a delay to get updated stats
      setTimeout(() => qc.invalidateQueries({ queryKey: keys.symbolSources }), 3000)
    },
  })
}

export function useDeleteSymbolSource() {
  return useInvalidatingMutation(
    (id: number) => api.symbolSources.delete(id),
    [keys.symbolSources],
  )
}

