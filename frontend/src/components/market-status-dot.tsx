import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

const STATE_CONFIG: Record<string, { color: string; label: string }> = {
  PRE: { color: "bg-blue-500", label: "Pre-market" },
  PREPRE: { color: "bg-blue-500", label: "Pre-market" },
  REGULAR: { color: "bg-emerald-500", label: "Market open" },
  POST: { color: "bg-orange-500", label: "After-hours" },
  POSTPOST: { color: "bg-orange-500", label: "After-hours" },
  CLOSED: { color: "bg-red-500", label: "Closed" },
}

const DEFAULT_CONFIG = { color: "bg-red-500", label: "Closed" }

export function MarketStatusDot({
  marketState,
  className,
}: {
  marketState: string | null | undefined
  className?: string
}) {
  const config = (marketState && STATE_CONFIG[marketState]) || DEFAULT_CONFIG

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn("inline-block h-2 w-2 rounded-full shrink-0", config.color, className)}
          />
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          {config.label}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
