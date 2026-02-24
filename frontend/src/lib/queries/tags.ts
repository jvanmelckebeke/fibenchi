import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api, type Asset, type TagCreate } from "../api"
import { keys, STALE_5MIN, useInvalidatingMutation } from "./shared"
import { useQuery } from "@tanstack/react-query"

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
