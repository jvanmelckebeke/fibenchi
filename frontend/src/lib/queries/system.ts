import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

import { keys, useInvalidatingMutation } from "./shared"

export function useDataHealth() {
  // Fresh-ish without hammering: the heal state only changes on 10-min job
  // ticks, so a 60s refetch keeps the countdown honest.
  return useQuery({
    queryKey: keys.dataHealth,
    queryFn: api.system.dataHealth,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

export function useSystemStats() {
  return useQuery({
    queryKey: keys.systemStats,
    queryFn: api.system.stats,
    staleTime: 60_000,
  })
}

export function useOrphans() {
  return useQuery({
    queryKey: keys.orphans,
    queryFn: api.system.orphans,
    staleTime: 60_000,
  })
}

const ORPHAN_KEYS = [keys.orphans, keys.systemStats, keys.assets, keys.groups, keys.theses]

export function useDeleteOrphan() {
  return useInvalidatingMutation((assetId: number) => api.system.deleteOrphan(assetId), ORPHAN_KEYS)
}

/** Re-adopt an orphan into a group — it stops being an orphan. */
export function useAdoptOrphanToGroup() {
  return useInvalidatingMutation(
    ({ groupId, assetId }: { groupId: number; assetId: number }) =>
      api.groups.addAssets(groupId, [assetId]),
    ORPHAN_KEYS,
  )
}

/** Re-adopt an orphan into a thesis — it stops being an orphan. */
export function useAdoptOrphanToThesis() {
  return useInvalidatingMutation(
    ({ thesisId, assetId }: { thesisId: number; assetId: number }) =>
      api.theses.addAssets(thesisId, [assetId]),
    ORPHAN_KEYS,
  )
}
