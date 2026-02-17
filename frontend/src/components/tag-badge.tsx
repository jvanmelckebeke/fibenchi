import { cn } from "@/lib/utils"

export function TagBadge({
  name,
  color,
  active = true,
  onClick,
  onRemove,
}: {
  name: string
  color: string
  active?: boolean
  onClick?: () => void
  onRemove?: () => void
}) {
  const Wrapper = onClick ? "button" : "span"
  return (
    <Wrapper
      type={onClick ? "button" : undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition-all",
        onClick && "cursor-pointer",
        active
          ? "bg-secondary text-secondary-foreground"
          : "bg-muted/50 text-muted-foreground opacity-60"
      )}
      onClick={onClick}
    >
      <span
        className="h-2 w-2 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      {name}
      {onRemove && (
        <button
          type="button"
          className="ml-0.5 text-muted-foreground hover:text-foreground"
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
        >
          &times;
        </button>
      )}
    </Wrapper>
  )
}
