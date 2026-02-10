import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, RefreshCw, Trash2, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { PriceChart } from "@/components/price-chart"
import {
  usePrices,
  useIndicators,
  useRefreshPrices,
  useThesis,
  useUpdateThesis,
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
} from "@/lib/queries"

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [period, setPeriod] = useState<string>("1y")

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} period={period} setPeriod={setPeriod} />
      <ChartSection symbol={symbol} period={period} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ThesisSection symbol={symbol} />
        <AnnotationsSection symbol={symbol} />
      </div>
    </div>
  )
}

function Header({
  symbol,
  period,
  setPeriod,
}: {
  symbol: string
  period: string
  setPeriod: (p: string) => void
}) {
  const refresh = useRefreshPrices(symbol)

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">{symbol}</h1>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <Button
              key={p}
              variant={period === p ? "default" : "ghost"}
              size="sm"
              onClick={() => setPeriod(p)}
              className="text-xs"
            >
              {p}
            </Button>
          ))}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refresh.isPending ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>
    </div>
  )
}

function ChartSection({ symbol, period }: { symbol: string; period: string }) {
  const { data: prices, isLoading: pricesLoading } = usePrices(symbol, period)
  const { data: indicators, isLoading: indicatorsLoading } = useIndicators(symbol, period)
  const { data: annotations } = useAnnotations(symbol)

  if (pricesLoading || indicatorsLoading) {
    return <div className="h-[520px] flex items-center justify-center text-muted-foreground">Loading chart...</div>
  }

  if (!prices?.length) {
    return (
      <div className="h-[520px] flex items-center justify-center text-muted-foreground">
        No price data. Click Refresh to fetch.
      </div>
    )
  }

  return <PriceChart prices={prices} indicators={indicators ?? []} annotations={annotations ?? []} />
}

function ThesisSection({ symbol }: { symbol: string }) {
  const { data: thesis } = useThesis(symbol)
  const updateThesis = useUpdateThesis(symbol)
  const [editing, setEditing] = useState(false)
  const [content, setContent] = useState("")

  const handleEdit = () => {
    setContent(thesis?.content ?? "")
    setEditing(true)
  }

  const handleSave = () => {
    updateThesis.mutate(content, { onSuccess: () => setEditing(false) })
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Investment Thesis</CardTitle>
        {editing ? (
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={updateThesis.isPending}>
              Save
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={handleEdit}>
            Edit
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {editing ? (
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="min-h-[200px] font-mono text-sm"
            placeholder="Write your investment thesis in markdown..."
          />
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none min-h-[100px]">
            {thesis?.content ? (
              <pre className="whitespace-pre-wrap font-sans text-sm">{thesis.content}</pre>
            ) : (
              <p className="text-muted-foreground italic">No thesis yet. Click Edit to write one.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AnnotationsSection({ symbol }: { symbol: string }) {
  const { data: annotations } = useAnnotations(symbol)
  const createAnnotation = useCreateAnnotation(symbol)
  const deleteAnnotation = useDeleteAnnotation(symbol)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ date: "", title: "", body: "", color: "#3b82f6" })

  const handleAdd = () => {
    if (!form.date || !form.title) return
    createAnnotation.mutate(
      { date: form.date, title: form.title, body: form.body || undefined, color: form.color },
      {
        onSuccess: () => {
          setForm({ date: "", title: "", body: "", color: "#3b82f6" })
          setAdding(false)
        },
      }
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Annotations</CardTitle>
        <Button size="sm" variant="ghost" onClick={() => setAdding(!adding)}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {adding && (
          <div className="space-y-2 p-3 rounded-md border bg-muted/30">
            <div className="flex gap-2">
              <Input
                type="date"
                value={form.date}
                onChange={(e) => setForm({ ...form, date: e.target.value })}
                className="w-40"
              />
              <Input
                placeholder="Title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                className="h-9 w-9 rounded border cursor-pointer"
              />
            </div>
            <Textarea
              placeholder="Notes (optional)"
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
              className="min-h-[60px]"
            />
            <div className="flex justify-end gap-1">
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleAdd} disabled={createAnnotation.isPending}>
                Save
              </Button>
            </div>
          </div>
        )}

        {annotations?.length === 0 && !adding && (
          <p className="text-sm text-muted-foreground italic">No annotations yet.</p>
        )}

        {annotations?.map((a) => (
          <div key={a.id} className="flex items-start gap-3 group">
            <div
              className="mt-1.5 h-3 w-3 rounded-full shrink-0"
              style={{ backgroundColor: a.color }}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{a.title}</span>
                <Badge variant="secondary" className="text-xs">
                  {a.date}
                </Badge>
              </div>
              {a.body && <p className="text-xs text-muted-foreground mt-0.5">{a.body}</p>}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => deleteAnnotation.mutate(a.id)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
