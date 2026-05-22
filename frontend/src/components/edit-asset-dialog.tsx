import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { useUpdateAsset } from "@/lib/queries"
import type { Asset, AssetType } from "@/lib/api"

/** Only the fields the edit form reads/writes — callers needn't supply a full Asset. */
type EditableAsset = Pick<Asset, "id" | "symbol" | "name" | "type" | "currency">

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

function EditAssetForm({ asset, onClose }: { asset: EditableAsset; onClose: () => void }) {
  const updateAsset = useUpdateAsset()
  const [name, setName] = useState(asset.name)
  const [type, setType] = useState<AssetType>(asset.type)
  const [currency, setCurrency] = useState(asset.currency)

  const dirty =
    name.trim() !== asset.name ||
    type !== asset.type ||
    currency.trim().toUpperCase() !== asset.currency.toUpperCase()

  const handleSave = () => {
    if (!name.trim() || !currency.trim()) return
    updateAsset.mutate(
      {
        id: asset.id,
        data: {
          name: name.trim() !== asset.name ? name.trim() : undefined,
          type: type !== asset.type ? type : undefined,
          currency:
            currency.trim().toUpperCase() !== asset.currency.toUpperCase()
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
          <Label htmlFor="asset-currency">Currency</Label>
          <Input
            id="asset-currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            maxLength={10}
            placeholder="USD, EUR, GBP, ..."
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={!dirty || !name.trim() || !currency.trim() || updateAsset.isPending}
        >
          Save
        </Button>
      </DialogFooter>
    </>
  )
}

export function EditAssetDialog({ asset, open, onOpenChange }: EditAssetDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        {asset && (
          <EditAssetForm
            key={asset.id}
            asset={asset}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
