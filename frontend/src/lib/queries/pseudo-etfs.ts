import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, type PseudoETFCreate, type PseudoETFUpdate, type AnnotationCreate } from "../api"
import { keys, STALE_5MIN, useInvalidatingMutation } from "./shared"

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
