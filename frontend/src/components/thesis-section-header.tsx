import type { ReactNode } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import type { Thesis, ThesisStatus, ThesisPerformancePoint } from "@/lib/api"
import { formatChangePct, formatDateLong, readableTextColor } from "@/lib/format"
import { resolveIcon } from "@/lib/icon-utils"
import { ContextActionable, type ContextAction } from "@/components/context-actionable"
import { MiniSparkline } from "@/components/mini-sparkline"

const STATUS_STYLES: Record<ThesisStatus, { label: string; className: string }> = {
  live: { label: "Live", className: "bg-emerald-500/15 text-emerald-500" },
  watching: { label: "Watching", className: "bg-amber-500/15 text-amber-500" },
  played_out: { label: "Played out", className: "bg-muted text-muted-foreground" },
}

export function StatusBadge({ status }: { status: ThesisStatus }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.watching
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${s.className}`}>
      {s.label}
    </span>
  )
}

interface ThesisSectionHeaderProps {
  thesis: Thesis
  /** When `onToggle` is provided the header is a button that expands the section. */
  expanded?: boolean
  onToggle?: () => void
  memberCount?: number
  performance?: ThesisPerformancePoint[]
  /** Trailing actions (e.g. an edit button) — rendered outside the toggle button. */
  actions?: ReactNode
  /** Right-click actions for the header (generated into a context menu). */
  contextActions?: ContextAction[]
}

/**
 * The thesis "card" header: coloured icon chip, name, status, opened date and
 * aggregate return. Shared between the per-group sections view (static header +
 * edit action) and the all-theses page (collapsible, with member count + a
 * performance sparkline).
 */
export function ThesisSectionHeader({
  thesis,
  expanded,
  onToggle,
  memberCount,
  performance,
  actions,
  contextActions,
}: ThesisSectionHeaderProps) {
  const ThesisIcon = resolveIcon(thesis.icon ?? "lightbulb")
  const agg = formatChangePct(thesis.aggregate_pct)

  const content = (
    <>
      {onToggle &&
        (expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        ))}
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
        style={{ backgroundColor: thesis.color }}
        aria-hidden
      >
        {/* eslint-disable-next-line react-hooks/static-components -- resolveIcon returns stable refs from lucide's icon map */}
        <ThesisIcon className="h-4 w-4" style={{ color: readableTextColor(thesis.color) }} />
      </span>
      <h3 className="font-semibold">{thesis.name}</h3>
      <StatusBadge status={thesis.status} />
      {memberCount != null && (
        <span className="text-xs text-muted-foreground">
          {memberCount} {memberCount === 1 ? "ticker" : "tickers"}
        </span>
      )}
      <span className="text-xs text-muted-foreground">opened {formatDateLong(thesis.opened_at)}</span>
      {agg.text && (
        <span
          className={`text-sm font-medium ${agg.className}`}
          title="Equal-weight return since opened, across all members"
        >
          {agg.text}
        </span>
      )}
      {performance && performance.length > 1 && (
        <MiniSparkline points={performance} className="ml-1 text-muted-foreground" />
      )}
    </>
  )

  const header = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {onToggle ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-left"
        >
          {content}
        </button>
      ) : (
        content
      )}
      {actions && <div className="ml-auto shrink-0">{actions}</div>}
    </div>
  )

  return <ContextActionable actions={contextActions}>{header}</ContextActionable>
}
