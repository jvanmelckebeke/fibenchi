import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { marketState, type MarketState } from "@/lib/market-state"

export function MarketStatusDot({
  marketState: state,
  className,
}: {
  marketState: MarketState | null | undefined
  className?: string
}) {
  const { dotColor, label } = marketState(state)

  return (
    <Tooltip delayDuration={300}>
      <TooltipTrigger asChild>
        <span
          className={cn("inline-block h-2 w-2 rounded-full shrink-0", dotColor, className)}
        />
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  )
}
