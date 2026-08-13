import { useState } from "react"
import {
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { EntityDialog } from "@/components/entity-dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useResetAssetDetection, useUpdateAsset } from "@/lib/queries"
import { AssetSuggestionBanner } from "@/components/assets/asset-suggestion-banner"
import type { Asset, AssetType, UnitKind } from "@/lib/api"

/** Only the fields the edit form reads/writes — callers needn't supply a full Asset. */
type EditableAsset = Pick<Asset, "id" | "symbol" | "name" | "type" | "currency" | "unit_kind"> &
  Partial<Pick<Asset, "suggested">>

interface EditAssetDialogProps {
  asset: EditableAsset | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const TYPE_OPTIONS: { value: AssetType; label: string }[] = [
  { value: "stock", label: "Stock" },
  { value: "etf", label: "ETF" },
  { value: "index", label: "Index" },
]

// Unit answers "how does this number read", which currency alone can't: it
// only ever says *which* currency, so an index had to claim a denomination it
// doesn't have. Percent used to be a hardcoded four-ticker list in format.ts,
// unreachable from here.
const UNIT_OPTIONS: { value: UnitKind; label: string; hint: string }[] = [
  { value: "currency", label: "Currency", hint: "$71.40" },
  { value: "percent", label: "Percent", hint: "4.63%" },
  { value: "points", label: "Points", hint: "6,912.34" },
]

function EditAssetForm({ asset, onClose }: { asset: EditableAsset; onClose: () => void }) {
  const updateAsset = useUpdateAsset()
  const resetDetection = useResetAssetDetection()
  const [name, setName] = useState(asset.name)
  const [type, setType] = useState<AssetType>(asset.type)
  const [currency, setCurrency] = useState(asset.currency)
  const [unitKind, setUnitKind] = useState<UnitKind>(asset.unit_kind)

  // Currency only means anything when the number *is* money; for a rate or an
  // index level there is nothing to denominate.
  const currencyApplies = unitKind === "currency"

  const dirty =
    name.trim() !== asset.name ||
    type !== asset.type ||
    unitKind !== asset.unit_kind ||
    (currencyApplies && currency.trim().toUpperCase() !== asset.currency.toUpperCase())

  // Applying is just a normal edit — which is also what records it as your
  // choice, so the banner won't come back.
  const applySuggestion = () => {
    const s = asset.suggested
    if (!s) return
    if (s.disagrees.includes("type")) setType(s.type)
    if (s.disagrees.includes("unit_kind")) setUnitKind(s.unit_kind)
  }

  // Resetting is the inverse of an edit and has to go straight to the server:
  // it clears the user flag, which no PATCH of a value could express. Local
  // form state follows so the dialog doesn't sit on a stale selection.
  const handleReset = () => {
    const s = asset.suggested
    if (!s) return
    const fields = s.differs.filter((f) => !s.disagrees.includes(f))
    resetDetection.mutate(
      { id: asset.id, fields },
      {
        onSuccess: (updated) => {
          setType(updated.type)
          setUnitKind(updated.unit_kind)
          setCurrency(updated.currency)
        },
      },
    )
  }

  const handleSave = () => {
    if (!name.trim() || (currencyApplies && !currency.trim())) return
    updateAsset.mutate(
      {
        id: asset.id,
        data: {
          name: name.trim() !== asset.name ? name.trim() : undefined,
          type: type !== asset.type ? type : undefined,
          unit_kind: unitKind !== asset.unit_kind ? unitKind : undefined,
          currency:
            currencyApplies && currency.trim().toUpperCase() !== asset.currency.toUpperCase()
              ? currency.trim().toUpperCase()
              : undefined,
        },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit {asset.symbol}</DialogTitle>
      </DialogHeader>
      <div className="space-y-4 py-2">
        <AssetSuggestionBanner
          suggestion={asset.suggested}
          onApply={applySuggestion}
          onReset={handleReset}
          resetPending={resetDetection.isPending}
        />
        <div className="space-y-2">
          <Label htmlFor="asset-name">Name</Label>
          <Input
            id="asset-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="asset-type">Type</Label>
          <Select value={type} onValueChange={(v) => setType(v as AssetType)}>
            <SelectTrigger id="asset-type" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="asset-unit">Unit</Label>
          <Select value={unitKind} onValueChange={(v) => setUnitKind(v as UnitKind)}>
            <SelectTrigger id="asset-unit" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {UNIT_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                  <span className="ml-2 font-mono text-[11px] text-muted-foreground">{opt.hint}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {/* Hidden rather than disabled when it doesn't apply: a greyed-out
            field still implies the asset has a currency, which is the exact
            confusion this whole change is undoing. */}
        {currencyApplies && (
          <div className="space-y-2">
            <Label htmlFor="asset-currency">Currency</Label>
            <Input
              id="asset-currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              maxLength={10}
              placeholder="USD, EUR, GBP, ..."
            />
          </div>
        )}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={!dirty || !name.trim() || (currencyApplies && !currency.trim()) || updateAsset.isPending}
        >
          Save
        </Button>
      </DialogFooter>
    </>
  )
}

export function EditAssetDialog({ asset, open, onOpenChange }: EditAssetDialogProps) {
  return (
    <EntityDialog entity={asset} open={open} onOpenChange={onOpenChange} contentClassName="sm:max-w-[400px]">
      {(asset, close) => <EditAssetForm asset={asset} onClose={close} />}
    </EntityDialog>
  )
}
