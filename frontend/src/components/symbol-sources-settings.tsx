import { useState } from "react"
import { Database, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  useSymbolSources,
  useSymbolSourceProviders,
  useCreateSymbolSource,
  useUpdateSymbolSource,
  useSyncSymbolSource,
  useDeleteSymbolSource,
} from "@/lib/queries"
import type { SymbolSource } from "@/lib/api"

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function SourceCard({ source }: { source: SymbolSource }) {
  const updateSource = useUpdateSymbolSource()
  const syncSource = useSyncSymbolSource()
  const deleteSource = useDeleteSymbolSource()

  const enabledMarkets = new Set<string>((source.config.markets as string[]) ?? [])

  const handleToggleEnabled = (enabled: boolean) => {
    updateSource.mutate({ id: source.id, data: { enabled } })
  }

  const handleToggleMarket = (market: string) => {
    const next = new Set(enabledMarkets)
    if (next.has(market)) next.delete(market)
    else next.add(market)
    updateSource.mutate({
      id: source.id,
      data: { config: { ...source.config, markets: [...next] } },
    })
  }

  const handleSync = () => syncSource.mutate(source.id)
  const handleDelete = () => deleteSource.mutate(source.id)

  // Available markets for this provider type
  const { data: providers } = useSymbolSourceProviders()
  const providerInfo = providers?.[source.provider_type]
  const availableMarkets = providerInfo?.markets ?? []

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{source.name}</span>
          <span className="text-xs text-muted-foreground rounded-full bg-muted px-2 py-0.5">
            {source.symbol_count.toLocaleString()} symbols
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1.5"
            onClick={handleSync}
            disabled={syncSource.isPending}
          >
            {syncSource.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
            {syncSource.isPending ? "Syncing..." : "Sync Now"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
            onClick={handleDelete}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Switch
            id={`source-${source.id}-enabled`}
            checked={source.enabled}
            onCheckedChange={handleToggleEnabled}
          />
          <Label htmlFor={`source-${source.id}-enabled`} className="text-xs">
            {source.enabled ? "Enabled" : "Disabled"}
          </Label>
        </div>
        {source.last_synced_at && (
          <span>Last synced: {formatRelativeTime(source.last_synced_at)}</span>
        )}
        {!source.last_synced_at && <span>Never synced</span>}
      </div>

      {availableMarkets.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">Markets:</span>
          <div className="flex flex-wrap gap-1.5">
            {availableMarkets.map((m) => {
              const active = enabledMarkets.size === 0 || enabledMarkets.has(m.key)
              return (
                <button
                  key={m.key}
                  onClick={() => handleToggleMarket(m.key)}
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    active
                      ? "bg-primary/10 text-primary border border-primary/20"
                      : "bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {m.label.replace("Euronext ", "").replace("Oslo Børs", "Oslo")}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export function SymbolSourcesSettings() {
  const { data: sources, isLoading } = useSymbolSources()
  const { data: providers } = useSymbolSourceProviders()
  const createSource = useCreateSymbolSource()
  const [adding, setAdding] = useState(false)
  const [newProviderType, setNewProviderType] = useState("")

  const providerKeys = providers ? Object.keys(providers) : []
  // Filter out providers that already have a source
  const existingTypes = new Set(sources?.map((s) => s.provider_type) ?? [])
  const availableProviders = providerKeys.filter((k) => !existingTypes.has(k))

  const handleAdd = () => {
    if (!newProviderType || !providers) return
    const info = providers[newProviderType]
    createSource.mutate(
      {
        name: info.label,
        provider_type: newProviderType,
        config: { markets: info.markets.map((m) => m.key) },
      },
      {
        onSuccess: () => {
          setAdding(false)
          setNewProviderType("")
        },
      },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Symbol Sources</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Pre-seed the symbol directory with exchange listings for instant search results.
        </p>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading...
          </div>
        )}

        {sources?.map((source) => <SourceCard key={source.id} source={source} />)}

        {sources && sources.length === 0 && !adding && (
          <p className="text-sm text-muted-foreground py-2">
            No sources configured. Add one to enable instant symbol search.
          </p>
        )}

        {adding ? (
          <div className="flex items-center gap-2">
            <Select value={newProviderType} onValueChange={setNewProviderType}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Provider..." />
              </SelectTrigger>
              <SelectContent>
                {availableProviders.map((key) => (
                  <SelectItem key={key} value={key}>
                    {providers?.[key]?.label ?? key}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" onClick={handleAdd} disabled={!newProviderType || createSource.isPending}>
              {createSource.isPending ? "Adding..." : "Add"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setAdding(false); setNewProviderType("") }}>
              Cancel
            </Button>
          </div>
        ) : (
          availableProviders.length > 0 && (
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setAdding(true)}>
              <Plus className="h-3.5 w-3.5" />
              Add Source
            </Button>
          )
        )}
      </CardContent>
    </Card>
  )
}
