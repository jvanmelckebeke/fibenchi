import { useQuery } from "@tanstack/react-query"
import { api, type AnnotationCreate } from "../api"
import { keys, STALE_5MIN, useInvalidatingMutation } from "./shared"

// Note
export function useNote(symbol: string) {
  return useQuery({
    queryKey: keys.note(symbol),
    queryFn: () => api.note.get(symbol),
    enabled: !!symbol,
    staleTime: STALE_5MIN,
  })
}

export function useUpdateNote(symbol: string) {
  return useInvalidatingMutation(
    (content: string) => api.note.update(symbol, content),
    [keys.note(symbol)],
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
