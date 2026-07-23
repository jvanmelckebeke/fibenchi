import type { Asset, Group } from "@/lib/api"

/**
 * Index every group's assets by id (first occurrence wins). Used to resolve
 * thesis members — which only carry id/symbol/name — back to full Asset rows
 * for the group table.
 */
export function buildAssetsById(groups: Group[]): Map<number, Asset> {
  const map = new Map<number, Asset>()
  for (const g of groups) for (const a of g.assets) if (!map.has(a.id)) map.set(a.id, a)
  return map
}
