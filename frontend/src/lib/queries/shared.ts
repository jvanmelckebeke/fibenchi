import { useMutation, useQueryClient } from "@tanstack/react-query"

export const STALE_5MIN = 5 * 60_000
export const STALE_24H = 24 * 60 * 60_000

export function useInvalidatingMutation<TData, TVariables>(
  mutationFn: (vars: TVariables) => Promise<TData>,
  invalidateKeys: readonly (readonly unknown[])[],
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      for (const key of invalidateKeys) {
        qc.invalidateQueries({ queryKey: key })
      }
    },
  })
}

export const keys = {
  portfolioIndex: (period?: string) => ["portfolio-index", period] as const,
  portfolioPerformers: (period?: string) => ["portfolio-performers", period] as const,
  assets: ["assets"] as const,
  assetDetail: (symbol: string, period?: string) => ["asset-detail", symbol, period] as const,
  etfHoldings: (symbol: string) => ["etf-holdings", symbol] as const,
  holdingsIndicators: (symbol: string) => ["holdings-indicators", symbol] as const,
  tags: ["tags"] as const,
  groups: ["groups"] as const,
  group: (id: number) => ["groups", id] as const,
  groupSparklines: (id: number, period?: string) => ["group-sparklines", id, period] as const,
  groupIndicators: (id: number) => ["group-indicators", id] as const,
  thesis: (symbol: string) => ["thesis", symbol] as const,
  annotations: (symbol: string) => ["annotations", symbol] as const,
  pseudoEtfs: ["pseudo-etfs"] as const,
  pseudoEtf: (id: number) => ["pseudo-etfs", id] as const,
  pseudoEtfPerformance: (id: number) => ["pseudo-etfs", id, "performance"] as const,
  pseudoEtfConstituentsIndicators: (id: number) => ["pseudo-etfs", id, "constituents-indicators"] as const,
  pseudoEtfThesis: (id: number) => ["pseudo-etfs", id, "thesis"] as const,
  pseudoEtfAnnotations: (id: number) => ["pseudo-etfs", id, "annotations"] as const,
  symbolSearchLocal: (q: string) => ["symbol-search-local", q] as const,
  symbolSearchYahoo: (q: string) => ["symbol-search-yahoo", q] as const,
  symbolSources: ["symbol-sources"] as const,
  symbolSourceProviders: ["symbol-source-providers"] as const,
}
