import { useEffect, useMemo, useRef, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { RAMP_COLORS, pctSpan, sigmaUnit } from "./color-scale"
import type { ColorMode } from "./color-scale"
import { packSections } from "./paging"
import { BoardTile, PhaseIcon } from "./tile"
import type { BoardSection } from "./use-board-data"

// Geometry per breakpoint, mirroring the tile/grid Tailwind classes. Row =
// tile height + gap; header = section title + margins + inter-section gap.
const GEOM = {
  compact: { minTile: 104, gap: 3, rowPx: 65, headerPx: 42 },
  full: { minTile: 140, gap: 4, rowPx: 84, headerPx: 48 },
}
// Footer row top margin + page bottom padding + a small buffer, on top of
// the *measured* legend/pager height (it wraps taller at narrow widths).
const FOOTER_EXTRA_PX = 36

/** Measure the pixel budget under the board's top edge and pack whole
 * sections into screen-sized pages. Re-packs on any resize. The footer
 * (legend + pager) is measured, not assumed — at narrow widths it wraps. */
function usePagedSections(sections: BoardSection[]) {
  const ref = useRef<HTMLDivElement>(null)
  const footerRef = useRef<HTMLDivElement>(null)
  const [metrics, setMetrics] = useState({ width: 0, availPx: 0, full: false })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      const rect = el.getBoundingClientRect()
      const footerH = footerRef.current?.offsetHeight ?? 32
      setMetrics({
        width: rect.width,
        availPx: Math.max(240, window.innerHeight - rect.top - footerH - FOOTER_EXTRA_PX),
        full: window.matchMedia("(min-width: 1536px)").matches,
      })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    if (footerRef.current) ro.observe(footerRef.current)
    window.addEventListener("resize", measure)
    return () => {
      ro.disconnect()
      window.removeEventListener("resize", measure)
    }
  }, [])

  const pages = useMemo(() => {
    const g = metrics.full ? GEOM.full : GEOM.compact
    const cols = Math.max(1, Math.floor((metrics.width + g.gap) / (g.minTile + g.gap)))
    return packSections(sections, { cols, rowPx: g.rowPx, headerPx: g.headerPx, availPx: metrics.availPx })
  }, [sections, metrics])

  return { ref, footerRef, pages, availPx: metrics.availPx }
}

export function Board({ sections, mode }: { sections: BoardSection[]; mode: ColorMode }) {
  // Day-adaptive scale: computed over the whole board — every page and
  // section shares one ramp (per-page scales would make colours incomparable).
  const span = useMemo(() => {
    const tiles = sections.flatMap((s) => s.tiles)
    if (mode === "sigma")
      return 3 * sigmaUnit(tiles.map((t) => t.sigma).filter((v): v is number => v != null))
    return pctSpan(tiles.map((t) => t.todayPct).filter((v): v is number => v != null))
  }, [sections, mode])

  const { ref, footerRef, pages, availPx } = usePagedSections(sections)
  const [page, setPage] = useState(0)
  const current = Math.min(page, Math.max(0, pages.length - 1))
  const visible = pages[current] ?? []

  // Arrow keys page too (ignored while typing anywhere).
  useEffect(() => {
    if (pages.length < 2) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return
      if (e.key === "ArrowLeft") setPage((p) => Math.max(0, p - 1))
      if (e.key === "ArrowRight") setPage((p) => Math.min(pages.length - 1, p + 1))
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [pages.length])

  // The tile card is 272px against a 62px tile — four tiles across and about
  // two and a half tall, so it covers its neighbours. The delay makes it appear
  // when you *stop* on a tile rather than when you sweep past one;
  // skipDelayDuration keeps the next ones instant, so browsing stays fast once
  // you're already reading cards.
  return (
    <TooltipProvider delayDuration={450} skipDelayDuration={300}>
      {/* The section area is pinned to the measured page height, so the
          legend/pager row below it stays level across page flips. */}
      <div ref={ref}>
        <div className="space-y-5" style={pages.length > 1 ? { minHeight: availPx } : undefined}>
          {visible.map((s) => (
          <section key={s.key}>
            <h2 className="mb-1.5 flex items-center gap-2 text-xs font-medium 2xl:mb-2 2xl:text-[13px] text-muted-foreground">
              {s.accent && (
                <span aria-hidden className="h-4 w-[3px] rounded-full" style={{ backgroundColor: s.accent }} />
              )}
              {s.title}
              <span className="opacity-60">{s.tiles.length}</span>
            </h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-[3px] 2xl:grid-cols-[repeat(auto-fill,minmax(140px,1fr))] 2xl:gap-1">
              {s.tiles.map((t) => (
                <BoardTile key={t.symbol} tile={t} mode={mode} span={span} />
              ))}
            </div>
          </section>
          ))}
        </div>
        <div ref={footerRef} className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <Legend mode={mode} span={span} />
          {pages.length > 1 && (
            <Pager
              page={current}
              pageCount={pages.length}
              pages={pages}
              onPage={setPage}
            />
          )}
        </div>
      </div>
    </TooltipProvider>
  )
}

function Pager({
  page,
  pageCount,
  pages,
  onPage,
}: {
  page: number
  pageCount: number
  pages: BoardSection[][]
  onPage: (p: number) => void
}) {
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <button
        onClick={() => onPage(Math.max(0, page - 1))}
        disabled={page === 0}
        className="rounded p-1 hover:bg-muted disabled:opacity-30"
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {pages.map((p, i) => (
        <button
          key={i}
          onClick={() => onPage(i)}
          title={p.map((s) => s.title).join(" · ")}
          className={`rounded px-2 py-0.5 tabular-nums hover:bg-muted ${
            i === page ? "bg-muted font-medium text-foreground" : ""
          }`}
        >
          {i + 1}
        </button>
      ))}
      <button
        onClick={() => onPage(Math.min(pageCount - 1, page + 1))}
        disabled={page === pageCount - 1}
        className="rounded p-1 hover:bg-muted disabled:opacity-30"
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}

function Legend({ mode, span }: { mode: ColorMode; span: number }) {
  const unit = mode === "sigma" ? "σ" : "%"
  const fmt = () => (Number.isInteger(span) ? `${span}` : span.toFixed(1))
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="tabular-nums">-{fmt()}{unit}</span>
        <span
          className="h-3 w-36 rounded-[2px]"
          style={{ background: `linear-gradient(to right, ${RAMP_COLORS.join(", ")})` }}
        />
        <span className="tabular-nums">+{fmt()}{unit}</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span className="board-tile-unread h-3 w-5 rounded-[2px]" />
        no reading
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="open" /> open
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="premarket" /> pre
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="aftermarket" /> post
      </span>
      <span className="flex items-center gap-1.5">
        <PhaseIcon phase="closed" /> closed
      </span>
    </div>
  )
}
