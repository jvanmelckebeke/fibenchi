import { useMemo } from "react"
import { useAssets } from "@/lib/queries"

/**
 * Returns a Set of symbols that are already tracked (i.e. exist as assets).
 */
export function useTrackedSymbols(): Set<string> {
  const { data: assets } = useAssets()
  return useMemo(
    () => new Set(assets?.map((a) => a.symbol)),
    [assets],
  )
}
