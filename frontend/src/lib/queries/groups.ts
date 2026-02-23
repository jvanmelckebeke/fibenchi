import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, type Group, type GroupCreate, type GroupUpdate } from "../api"
import { keys, STALE_5MIN, useInvalidatingMutation } from "./shared"

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
