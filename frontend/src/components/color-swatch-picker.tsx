import { cn } from "@/lib/utils"
import { THESIS_PRESET_COLORS } from "@/lib/thesis-colors"

const SIZES = { sm: "h-4 w-4", md: "h-6 w-6" } as const

/**
 * A row of round colour swatches with a selection ring. Shared by the thesis
 * form and the tag-create affordance (previously three hand-rolled copies).
 */
export function ColorSwatchPicker({
  value,
  onChange,
  colors = THESIS_PRESET_COLORS,
  size = "md",
  className,
}: {
  value: string
  onChange: (color: string) => void
  colors?: readonly string[]
  size?: "sm" | "md"
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          aria-label={`Colour ${c}`}
          className={cn(
            SIZES[size],
            "rounded-full border-2",
            value === c ? "border-foreground" : "border-transparent",
          )}
          style={{ backgroundColor: c }}
          onClick={() => onChange(c)}
        />
      ))}
    </div>
  )
}
