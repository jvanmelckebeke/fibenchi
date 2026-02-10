import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, type AssetCreate, type GroupCreate, type GroupUpdate, type AnnotationCreate, type PseudoETFCreate, type PseudoETFUpdate } from "./api"

// Pseudo-ETF thesis/annotation keys are defined inline below

// Keys
export const keys = {
  assets: ["assets"] as const,
  asset: (symbol: string) => ["assets", symbol] as const,
  prices: (symbol: string, period?: string) => ["prices", symbol, period] as const,
  indicators: (symbol: string, period?: string) => ["indicators", symbol, period] as const,
  etfHoldings: (symbol: string) => ["etf-holdings", symbol] as const,
  groups: ["groups"] as const,
  thesis: (symbol: string) => ["thesis", symbol] as const,
  annotations: (symbol: string) => ["annotations", symbol] as const,
  pseudoEtfs: ["pseudo-etfs"] as const,
  pseudoEtf: (id: number) => ["pseudo-etfs", id] as const,
  pseudoEtfPerformance: (id: number) => ["pseudo-etfs", id, "performance"] as const,
  pseudoEtfThesis: (id: number) => ["pseudo-etfs", id, "thesis"] as const,
  pseudoEtfAnnotations: (id: number) => ["pseudo-etfs", id, "annotations"] as const,
}

// Assets
export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: api.assets.list })
}

export function useCreateAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AssetCreate) => api.assets.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.assets }),
  })
}

export function useDeleteAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (symbol: string) => api.assets.delete(symbol),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.assets }),
  })
}

// Prices & Indicators
export function usePrices(symbol: string, period?: string) {
  return useQuery({
    queryKey: keys.prices(symbol, period),
    queryFn: () => api.prices.list(symbol, period),
    enabled: !!symbol,
  })
}

export function useIndicators(symbol: string, period?: string) {
  return useQuery({
    queryKey: keys.indicators(symbol, period),
    queryFn: () => api.prices.indicators(symbol, period),
    enabled: !!symbol,
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

export function useRefreshPrices(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (period?: string) => api.prices.refresh(symbol, period),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.prices(symbol) })
      qc.invalidateQueries({ queryKey: keys.indicators(symbol) })
    },
  })
}

// Groups
export function useGroups() {
  return useQuery({ queryKey: keys.groups, queryFn: api.groups.list })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GroupCreate) => api.groups.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.groups }),
  })
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: GroupUpdate }) => api.groups.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.groups }),
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.groups.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.groups }),
  })
}

export function useAddAssetsToGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, assetIds }: { groupId: number; assetIds: number[] }) =>
      api.groups.addAssets(groupId, assetIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.groups }),
  })
}

export function useRemoveAssetFromGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, assetId }: { groupId: number; assetId: number }) =>
      api.groups.removeAsset(groupId, assetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.groups }),
  })
}

// Thesis
export function useThesis(symbol: string) {
  return useQuery({
    queryKey: keys.thesis(symbol),
    queryFn: () => api.thesis.get(symbol),
    enabled: !!symbol,
  })
}

export function useUpdateThesis(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => api.thesis.update(symbol, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.thesis(symbol) }),
  })
}

// Annotations
export function useAnnotations(symbol: string) {
  return useQuery({
    queryKey: keys.annotations(symbol),
    queryFn: () => api.annotations.list(symbol),
    enabled: !!symbol,
  })
}

export function useCreateAnnotation(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AnnotationCreate) => api.annotations.create(symbol, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.annotations(symbol) }),
  })
}

export function useDeleteAnnotation(symbol: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.annotations.delete(symbol, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.annotations(symbol) }),
  })
}

// Pseudo-ETFs
export function usePseudoEtfs() {
  return useQuery({ queryKey: keys.pseudoEtfs, queryFn: api.pseudoEtfs.list })
}

export function usePseudoEtf(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtf(id),
    queryFn: () => api.pseudoEtfs.get(id),
    enabled: !!id,
  })
}

export function useCreatePseudoEtf() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: PseudoETFCreate) => api.pseudoEtfs.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfs }),
  })
}

export function useUpdatePseudoEtf() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PseudoETFUpdate }) => api.pseudoEtfs.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfs }),
  })
}

export function useDeletePseudoEtf() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.pseudoEtfs.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfs }),
  })
}

export function useAddPseudoEtfConstituents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ etfId, assetIds }: { etfId: number; assetIds: number[] }) =>
      api.pseudoEtfs.addConstituents(etfId, assetIds),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.pseudoEtfs })
      qc.invalidateQueries({ queryKey: keys.pseudoEtfPerformance(vars.etfId) })
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

// Pseudo-ETF Thesis
export function usePseudoEtfThesis(id: number) {
  return useQuery({
    queryKey: keys.pseudoEtfThesis(id),
    queryFn: () => api.pseudoEtfs.thesis.get(id),
    enabled: !!id,
  })
}

export function useUpdatePseudoEtfThesis(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => api.pseudoEtfs.thesis.update(id, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfThesis(id) }),
  })
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
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AnnotationCreate) => api.pseudoEtfs.annotations.create(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfAnnotations(id) }),
  })
}

export function useDeletePseudoEtfAnnotation(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (annotationId: number) => api.pseudoEtfs.annotations.delete(id, annotationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.pseudoEtfAnnotations(id) }),
  })
}
