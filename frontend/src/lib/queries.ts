import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import { useCallback } from "react"
import { api, type Asset, type AssetCreate, type GroupCreate, type GroupUpdate, type TagCreate, type AnnotationCreate, type PseudoETFCreate, type PseudoETFUpdate, type SymbolSearchResult } from "./api"

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
  asset: (symbol: string) => ["assets", symbol] as const,
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
  watchlistSparklines: (period?: string) => ["watchlist-sparklines", period] as const,
  watchlistIndicators: ["watchlist-indicators"] as const,
  symbolSearch: (q: string) => ["symbol-search", q] as const,
}

// Portfolio
export function usePortfolioIndex(period?: string) {
  return useQuery({
    queryKey: keys.portfolioIndex(period),
    queryFn: () => api.portfolio.index(period),
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  })
}

export function usePortfolioPerformers(period?: string) {
  return useQuery({
    queryKey: keys.portfolioPerformers(period),
    queryFn: () => api.portfolio.performers(period),
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  })
}

// Watchlist batch
export function useWatchlistSparklines(period?: string) {
  return useQuery({
    queryKey: keys.watchlistSparklines(period),
    queryFn: () => api.watchlist.sparklines(period),
    staleTime: 5 * 60 * 1000,
  })
}

export function useWatchlistIndicators() {
  return useQuery({
    queryKey: keys.watchlistIndicators,
    queryFn: () => api.watchlist.indicators(),
    staleTime: 5 * 60 * 1000,
  })
}

// Assets
export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: api.assets.list, staleTime: 5 * 60 * 1000 })
}

export function useCreateAsset() {
  return useInvalidatingMutation(
    (data: AssetCreate) => api.assets.create(data),
    [keys.assets],
  )
}

export function useDeleteAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (symbol: string) => api.assets.delete(symbol),
    onMutate: async (symbol) => {
      await qc.cancelQueries({ queryKey: keys.assets })
      const previous = qc.getQueryData<Asset[]>(keys.assets)
      qc.setQueryData<Asset[]>(keys.assets, (old) =>
        old?.filter((a) => a.symbol !== symbol),
      )
      return { previous }
    },
    onError: (_err, _symbol, context) => {
      if (context?.previous) qc.setQueryData(keys.assets, context.previous)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.assets })
      qc.invalidateQueries({ queryKey: keys.groups })
    },
  })
}

// Search
export function useSymbolSearch(query: string) {
  return useQuery<SymbolSearchResult[]>({
    queryKey: keys.symbolSearch(query),
    queryFn: () => api.search(query),
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
    staleTime: 5 * 60 * 1000, // 5 min — daily OHLCV data, SSE handles live quotes
    placeholderData: keepPreviousData,
  })
}

export function useEtfHoldings(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.etfHoldings(symbol),
    queryFn: () => api.prices.holdings(symbol),
    enabled: !!symbol && enabled,
    staleTime: 24 * 60 * 60 * 1000, // cache 24h — holdings don't change often
  })
}

export function useHoldingsIndicators(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.holdingsIndicators(symbol),
    queryFn: () => api.prices.holdingsIndicators(symbol),
    enabled: !!symbol && enabled,
    staleTime: 5 * 60 * 1000, // cache 5 min
  })
}

export function useRefreshPrices(symbol: string) {
  return useInvalidatingMutation(
    (period?: string) => api.prices.refresh(symbol, period),
    [keys.assetDetail(symbol)],
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
        staleTime: 5 * 60 * 1000,
      }),
    [qc, period],
  )
}

// Tags
export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: api.tags.list, staleTime: 5 * 60 * 1000 })
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
  return useQuery({ queryKey: keys.groups, queryFn: api.groups.list, staleTime: 5 * 60 * 1000 })
}

export function useCreateGroup() {
  return useInvalidatingMutation(
    (data: GroupCreate) => api.groups.create(data),
    [keys.groups],
  )
}

export function useUpdateGroup() {
  return useInvalidatingMutation(
    ({ id, data }: { id: number; data: GroupUpdate }) => api.groups.update(id, data),
    [keys.groups],
  )
}

export function useDeleteGroup() {
  return useInvalidatingMutation(
    (id: number) => api.groups.delete(id),
    [keys.groups],
  )
}

export function useAddAssetsToGroup() {
  return useInvalidatingMutation(
    ({ groupId, assetIds }: { groupId: number; assetIds: number[] }) =>
      api.groups.addAssets(groupId, assetIds),
    [keys.groups],
  )
}

export function useRemoveAssetFromGroup() {
  return useInvalidatingMutation(
    ({ groupId, assetId }: { groupId: number; assetId: number }) =>
      api.groups.removeAsset(groupId, assetId),
    [keys.groups],
  )
}

export function useGroup(id: number) {
  return useQuery({
    queryKey: keys.group(id),
    queryFn: () => api.groups.get(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  })
}

export function useGroupSparklines(id: number, period?: string) {
  return useQuery({
    queryKey: keys.groupSparklines(id, period),
    queryFn: () => api.groups.sparklines(id, period),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  })
}

export function useGroupIndicators(id: number) {
  return useQuery({
    queryKey: keys.groupIndicators(id),
    queryFn: () => api.groups.indicators(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  })
}

// Thesis
export function useThesis(symbol: string) {
  return useQuery({
    queryKey: keys.thesis(symbol),
    queryFn: () => api.thesis.get(symbol),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
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
    staleTime: 5 * 60 * 1000,
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
  return useQuery({ queryKey: keys.pseudoEtfs, queryFn: api.pseudoEtfs.list, staleTime: 5 * 60 * 1000 })
}

export function usePseudoEtf(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtf(id),
    queryFn: () => api.pseudoEtfs.get(id),
    enabled: !!id,
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
  })
}

export function usePseudoEtfConstituentsIndicators(id: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.pseudoEtfConstituentsIndicators(id),
    queryFn: () => api.pseudoEtfs.constituentsIndicators(id),
    enabled: !!id && enabled,
    staleTime: 5 * 60 * 1000,
  })
}

// Pseudo-ETF Thesis
export function usePseudoEtfThesis(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtfThesis(id),
    queryFn: () => api.pseudoEtfs.thesis.get(id),
    enabled: !!id,
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

