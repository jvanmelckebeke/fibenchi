import { useState } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { usePseudoEtfs } from "@/lib/queries"
import { CreateForm } from "./create-form"
import { EtfCard } from "./etf-card"

export function PseudoEtfsPage() {
  const { data: etfs, isLoading } = usePseudoEtfs()
  const [creating, setCreating] = useState(false)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Pseudo-ETFs</h1>
        <Button onClick={() => setCreating(true)} disabled={creating}>
          <Plus className="h-4 w-4 mr-1.5" />
          New Pseudo-ETF
        </Button>
      </div>

      {creating && <CreateForm onClose={() => setCreating(false)} />}

      {isLoading && <p className="text-muted-foreground">Loading...</p>}

      {etfs && etfs.length === 0 && !creating && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <p>No pseudo-ETFs yet. Create one to track a custom basket of stocks.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {etfs?.map((etf) => (
          <EtfCard key={etf.id} etf={etf} />
        ))}
      </div>
    </div>
  )
}
