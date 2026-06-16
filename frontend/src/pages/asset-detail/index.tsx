import { useState } from "react"
import { useParams } from "react-router-dom"
import { ConnectedNote } from "@/components/connected-note"
import { ConnectedAnnotations } from "@/components/connected-annotations"
import { TagInput } from "@/components/tag-input"
import {
  useAssets,
  useAssetWindow,
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
  useNote,
  useUpdateNote,
} from "@/lib/queries"
import type { AssetWindow } from "@/lib/asset-window"
import { useSettings } from "@/lib/settings"
import { useQuote } from "@/lib/quote-stream"
import { StatsPanel } from "@/components/stats-panel"
import { Header, type ChartMode } from "./header"
import { ChartSection } from "./chart-section"
import { MovementStats } from "./movement-stats"
import { EarningsCountdown } from "@/components/earnings-countdown"
import { HoldingsSection } from "./holdings-section"


export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const { settings } = useSettings()
  const [assetWindow, setAssetWindow] = useState<AssetWindow>({
    kind: "period",
    period: settings.chart_default_period,
  })
  const [mode, setMode] = useState<ChartMode>("historical")
  const { data: assets } = useAssets()
  const asset = assets?.find((a) => a.symbol === symbol?.toUpperCase())
  const { prices, indicators, windowLabel } = useAssetWindow(symbol ?? "", assetWindow, {
    enabled: !!symbol && mode !== "live",
  })
  const quote = useQuote(symbol?.toUpperCase() ?? "")
  const isTracked = !!asset
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} name={asset?.name} currency={asset?.currency ?? "USD"} type={asset?.type ?? "stock"} assetWindow={assetWindow} setAssetWindow={setAssetWindow} isTracked={isTracked} assetId={asset?.id} mode={mode} setMode={setMode} />
      <ChartSection
        symbol={symbol}
        assetWindow={assetWindow}
        indicatorVisibility={settings.indicator_visibility}
        chartType={settings.chart_type}
        currency={asset?.currency}
        assetType={asset?.type}
        mode={mode}
      />
      {mode === "historical" && prices && prices.length > 1 && (
        <MovementStats
          prices={prices}
          label={windowLabel}
          symbol={symbol}
          currency={asset?.currency ?? "USD"}
          assetType={asset?.type ?? "stock"}
        />
      )}
      {mode === "historical" && indicators && indicators.length > 0 && (
        <StatsPanel
          indicators={indicators}
          indicatorVisibility={settings.indicator_visibility}
          currency={asset?.currency}
          quote={quote}
        />
      )}
      {!isEtf && <EarningsCountdown symbol={symbol} />}
      {isEtf && <HoldingsSection symbol={symbol} />}
      {isTracked && (
        <>
          <TagInput symbol={symbol} currentTags={asset?.tags ?? []} />
          <AssetAnnotations symbol={symbol} />
          <AssetNote symbol={symbol} />
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

function AssetNote({ symbol }: { symbol: string }) {
  const { data: note } = useNote(symbol)
  return (
    <ConnectedNote
      note={note}
      updateMutation={useUpdateNote(symbol)}
    />
  )
}
