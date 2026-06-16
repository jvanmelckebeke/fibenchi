import { useQuery } from "@tanstack/react-query"
import { api, type ThesisCreate, type ThesisUpdate } from "../api"
import { keys, STALE_5MIN, useInvalidatingMutation } from "./shared"

export function useTheses() {
  return useQuery({ queryKey: keys.theses, queryFn: api.theses.list, staleTime: STALE_5MIN })
}

export function useThesis(id: number) {
  return useQuery({
    queryKey: keys.thesis(id),
    queryFn: () => api.theses.get(id),
    enabled: !!id,
    staleTime: STALE_5MIN,
  })
}

export function useCreateThesis() {
  return useInvalidatingMutation(
    (data: ThesisCreate) => api.theses.create(data),
    [keys.theses],
  )
}

export function useUpdateThesis(id: number) {
  return useInvalidatingMutation(
    (data: ThesisUpdate) => api.theses.update(id, data),
    [keys.theses, keys.thesis(id)],
  )
}

export function useDeleteThesis() {
  return useInvalidatingMutation(
    (id: number) => api.theses.delete(id),
    [keys.theses],
  )
}

export function useAddThesisAssets(id: number) {
  return useInvalidatingMutation(
    (assetIds: number[]) => api.theses.addAssets(id, assetIds),
    [keys.theses, keys.thesis(id)],
  )
}

export function useRemoveThesisAsset(id: number) {
  return useInvalidatingMutation(
    (assetId: number) => api.theses.removeAsset(id, assetId),
    [keys.theses, keys.thesis(id)],
  )
}
