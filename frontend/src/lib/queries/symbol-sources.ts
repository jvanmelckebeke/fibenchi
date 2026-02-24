import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type SymbolSourceCreate, type SymbolSourceUpdate } from "../api"
import { keys, STALE_5MIN, STALE_24H, useInvalidatingMutation } from "./shared"

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
