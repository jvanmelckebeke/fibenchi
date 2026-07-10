import { cn } from "@/lib/utils"
import { formatChangePct } from "@/lib/format"

/**
 * A signed percentage change with the conventional green/red colouring, e.g.
 * "+1.23%". Wraps `formatChangePct` so call sites stop re-implementing the
 * `<span class="tabular-nums {colour}">{text ?? "—"}</span>` boilerplate.
 *
 * Extra span props (`ref`, `title`, …) pass through — `ref` drives the
 * price-flash animation at live sites.
 */
export function ChangePct({
  value,
  className,
  ...rest
}: {
  value: number | null
} & React.ComponentProps<"span">) {
  const { text, className: colorClass } = formatChangePct(value)
  return (
    <span className={cn("tabular-nums", colorClass, className)} {...rest}>
      {text ?? "—"}
    </span>
  )
}
