import { useState } from "react"
import { useParams } from "react-router-dom"
import { ConnectedThesis } from "@/components/connected-thesis"
import { ConnectedAnnotations } from "@/components/connected-annotations"
import { TagInput } from "@/components/tag-input"
import {
  useAssets,
  useAssetDetail,
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
  useThesis,
  useUpdateThesis,
} from "@/lib/queries"
import { useSettings } from "@/lib/settings"
import { StatsPanel } from "@/components/stats-panel"
import { Header } from "./header"
import { ChartSection } from "./chart-section"
import { HoldingsSection } from "./holdings-section"


export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const { settings } = useSettings()
  const [period, setPeriod] = useState<string>(settings.chart_default_period)
  const { data: assets } = useAssets()
  const asset = assets?.find((a) => a.symbol === symbol?.toUpperCase())
  const { data: detail } = useAssetDetail(symbol ?? "", period, { enabled: !!symbol })
  const isTracked = !!asset
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} name={asset?.name} currency={asset?.currency ?? "USD"} period={period} setPeriod={setPeriod} isTracked={isTracked} />
      <ChartSection
        symbol={symbol}
        period={period}
        indicatorVisibility={settings.indicator_visibility}
        chartType={settings.chart_type}
        currency={asset?.currency}
      />
      {detail?.indicators && detail.indicators.length > 0 && (
        <StatsPanel
          indicators={detail.indicators}
          indicatorVisibility={settings.indicator_visibility}
          currency={asset?.currency}
        />
      )}
      {isEtf && <HoldingsSection symbol={symbol} />}
      {isTracked && (
        <>
          <TagInput symbol={symbol} currentTags={asset?.tags ?? []} />
          <AssetAnnotations symbol={symbol} />
          <AssetThesis symbol={symbol} />
        </>
      )}
    </div>
  )
}

function AssetAnnotations({ symbol }: { symbol: string }) {
  const { data: annotations } = useAnnotations(symbol)
  return (
    <ConnectedAnnotations
      annotations={annotations}
      createMutation={useCreateAnnotation(symbol)}
      deleteMutation={useDeleteAnnotation(symbol)}
    />
  )
}

function AssetThesis({ symbol }: { symbol: string }) {
  const { data: thesis } = useThesis(symbol)
  return (
    <ConnectedThesis
      thesis={thesis}
      updateMutation={useUpdateThesis(symbol)}
    />
  )
}
