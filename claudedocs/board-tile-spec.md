# Dense board: session icons, tile tooltip, and a load audit

Against `origin/dev` at `6905986` (*feat(frontend): homepage dense board*). Three independent
changes plus an audit; they can land separately.

Files in play:

- `frontend/src/pages/portfolio/board/tile.tsx`
- `frontend/src/pages/portfolio/board/use-board-data.ts`
- `frontend/src/pages/portfolio/board/board.tsx` (legend only)
- `frontend/src/lib/queries/groups.ts` (audit fixes)

---

## 1 · Session-state icons: replace sunrise / sunset

### Why

Lucide's `sunrise` and `sunset` are **the same drawing**. Six of their eight paths are
byte-identical; a seventh (`M12 2v8` vs `M12 10V2`) is the same line drawn backwards, so it
renders identically. The only visible difference is an 8×4px chevron that flips direction — and
the tile renders these at 13–16px on a saturated background.

`Sun` and `Moon` work because they differ in **silhouette**: a radial burst versus a solid
crescent, still legible once the detail is gone. Sunrise and sunset differ only in *internal
detail*, and at 13px there is no internal detail left.

There's also a semantic problem worth recording: **up/down cannot distinguish pre from post.**
Both sit next to the horizon; only the direction of travel differs, and a static glyph can't show
travel without an arrow. The distinction has to move onto the **time axis** — left is before,
right is after — which a static shape *can* carry.

### The change

In `PhaseIcon`:

```diff
-import { Moon, Sun, Sunrise, Sunset } from "lucide-react"
+import { ArrowRightFromLine, ArrowRightToLine, Moon, Sun } from "lucide-react"
```

| phase | icon | reading |
|---|---|---|
| `open` | `Sun` (unchanged, keeps the ping) | — |
| `premarket` | `ArrowRightToLine` | arriving at the bell |
| `aftermarket` | `ArrowRightFromLine` | departed from the bell |
| `closed` | `Moon` (unchanged) | — |

Keep everything else about `PhaseIcon` as-is: same sizes (`h-3.5 w-3.5`, `2xl:h-4 2xl:w-4`),
same `opacity-80` on the non-open states, same `text-current` so the shape carries the state and
no hue competes with the value ramp.

The board legend in `board.tsx` renders through the same `PhaseIcon`, so it updates for free —
just confirm the labels still read right next to the new glyphs.

### Fix while you're in there

`PhaseIcon` sets a native `title={live ? "Open (live)" : "Open (scheduled)"}` on a span that sits
**inside** the Radix `TooltipTrigger`. Hovering the icon therefore shows the styled tooltip and
then, ~500 ms later, the browser's own tooltip on top of it. Drop the `title` — the live/scheduled
distinction moves into the tooltip body (§2). Keep the `aria-label`s.

---

## 2 · Tile tooltip

### The job

The board's whole value is that σ-Move makes 84 assets comparable. Its whole cost is that it is
dimensionless — the tile tells you *how unusual*, never *how much*. **The tooltip's job is to
un-normalise the tile**: hand back the magnitude, the recent path, and the context the grid had to
throw away.

Two rules follow, and they resolve most layout questions on their own:

1. **Lead with whatever the tile isn't showing.** In σ-mode the tile shows σ, so the tooltip leads
   with the % and the price. In %-mode it flips. Never open with a number the cursor is already on.
2. **A line either carries something no other line can, or it doesn't exist.** This is what removes
   the phase label from the meta row (the header already states it), the data-source note when the
   quote *is* live, and the section chips when the symbol is only in one section.

### What's wrong with the current one

**It's a white chip on a black board, and that costs more than glare.** `TooltipContent` uses
shadcn's default `bg-foreground text-background` — near-white surface, near-black ink. That makes
the app's finance colours unusable inside it: emerald-400 measures **1.86:1** on that surface,
red-400 **2.67:1**. On `bg-popover` they are 7.44:1 and 5.17:1. It's why the current tooltip prints
`+4.12%` in flat black while every other number on the page is coloured.

**It restates the tile.** Two of its five lines — symbol and σ — are already under the cursor.

**The sparkline is already in memory and thrown away.** `useWindowReturns` merges a 1-month
`SparklinePoint[]` per symbol, reduces it to three scalars, and drops the series.

**Minor:** the three windows are a run-on grey line where they should be an aligned column, and the
tooltip has no `tabular-nums` even though the tile does.

### Layout

272px wide. **Do not use the default `TooltipContent` surface** — this one needs
`bg-popover text-foreground`, a `border-border` hairline, a soft drop shadow, and `overflow-hidden`
so the section dividers reach the edges. Four sections separated by `border-t border-border`.

```
┌────────────────────────────────────────────┐
│ OKLO                      →|  pre-market   │  symbol: mono 13px/600
│ Oklo Inc.                                  │  name: 11.5px muted, wraps
├────────────────────────────────────────────┤
│ +2.41%    $71.40                   [+0.9σ] │  % 17px/600 up-down coloured
│ ▬▬▬▬▬▬▬▬▭▭▭▭▭       41/60 sessions         │  price 13px/500 muted
├────────────────────────────────────────────┤  σ pill: ramp colour + ink, ml-auto
│ ╱╲╱‾╲╱‾    1 week            +6.8%         │  warmup row: §3, warmup only
│            2 weeks           −1.2%         │
│            1 month          +18.4%         │
├────────────────────────────────────────────┤
│ [hotlist] [Thematic]                       │  chips only when >1 section
│ NYSE · opens 15:30 · 2h12                  │
│ phase from the calendar — no live quote    │  only when liveState === false
└────────────────────────────────────────────┘
```

Details:

- **σ pill** reuses `rampColor(sigma, span)` — same colour and ink as the tile itself, so the pill
  and the tile you're hovering agree. Right-aligned on the lead row via `ml-auto`.
- **Sparkline** 130×42, 1-month, area fill at ~10% opacity under a 1.4px stroke, `vector-effect:
  non-scaling-stroke`. Coloured by the sign of the 1-month return, not today's.
- **Windows** as a two-column table: label in `text-muted-foreground`, value right-aligned,
  `tabular-nums`, up/down coloured, one decimal.
- **Section chips** list every group (or thesis) the symbol belongs to. Render **only when the
  count is >1** — this is the one question only the tooltip can answer, and on the board several
  symbols appear in two sections. When it's one, the section header above the tile already says it.
- **Meta line** is `venue · next bell · countdown`. It does **not** repeat the phase; the header
  states it.
- **Source line** appears only when `tile.liveState === false`, in the warning colour: the phase
  came from `/api/market/phases` rather than a live quote. When it's live, say nothing.

### Data needed

Everything except one thing is already on `Tile`. **Nothing is fetched on hover** and nothing
should be — the tooltip must stay free.

- **Sparkline series** — return it from `useWindowReturns` alongside the scalars (it already builds
  `merged: Record<string, SparklinePoint[]>` and discards it), and add `spark: SparklinePoint[]` to
  the `Tile` interface.
- **Section membership** — derive from the same `groups` / `theses` data the roster is built from;
  add `sections: string[]` to `Tile`.

### Sizing and delay

272px against a 62px tile is four tiles across and about two and a half tall — it covers its
neighbours. Raise `delayDuration` on the board's `TooltipProvider` from `150` so the card appears
when you **stop** on a tile rather than when you sweep past it. Somewhere around 400–500 ms;
Radix's `skipDelayDuration` keeps the subsequent ones instant, so browsing stays fast once you're in.

---

## 3 · No σ reading: collapse four states into two

Today `reasonCopy()` renders four different prose strings. Collapse to **two shapes**, because
only one of the states implies a different action:

**Warmup** — the only no-reading state with a trajectory you can act on (wait), and the only one
whose progress is knowable. Show a 3px progress bar plus `41/60 sessions`, right-aligned mono,
sitting directly under the lead row.

The bar fills in **`--primary`** (teal) on a `--muted` track. It must **not** use the value ramp or
the gain/loss hues — this is system progress, not a reading, and it has to be visibly outside the
value language. The label does not say what the sessions are *for*: the em dash sits immediately
above it in the σ slot and establishes the subject without a word.

**Everything else** — `feed_behind`, `gap`, `unknown` — renders an **em dash where the σ pill would
go**, in `text-muted-foreground`, and nothing more. No prose, no reason string, no retry estimate.
All three resolve to the same user action, so they get the same shape.

The reading is missing; the day, the price, the path and the windows are not — those all still
render exactly as on a scored tile.

### Consequences upstream

- `reasonCopy()` in `tile.tsx` becomes dead code — delete it.
- `NoReadingReason` still needs its full discrimination **inside** `use-board-data.ts`:
  `feed_behind` vs `gap` decides whether σ is *withheld*, which is a different question from what
  the tooltip prints. But nothing downstream reads the distinction anymore. **Leave a comment
  saying so**, or the next person will read the unused variants as an oversight and "simplify" the
  cascade that keeps the board honest.
- What the tooltip actually needs from it collapses to
  `{ kind: "warmup"; bars: number; needed: number } | null`.

---

## 4 · Load audit

Cold load of the board, 84 distinct symbols across 9 groups:

| | requests | ~payload |
|---|---|---|
| `GET /groups` | 1 | 14 KB |
| `GET /theses` | 1 | 4 KB |
| `GET /indicators?symbols=…` (all 84) | 1 | 45 KB |
| `GET /groups/{id}/sparklines?period=1mo` | **9** | 75 KB |
| `GET /market/phases` (refetch 60 s) | 1 | 3 KB |
| `GET /system/data-health` (refetch 60 s) | 1 | <1 KB |
| `GET /portfolio/index?period=1y` | 1 | 7 KB |
| **total** | **15** + 1 SSE | **~150 KB** |

Everything except phases and health is `STALE_5MIN`, so navigating away and back inside five
minutes is free. This is not a heavy page — but four things are worth fixing.

**a · Sparklines are fetched per group instead of per roster.** Nine round trips covering 94
symbol-series to obtain 84 distinct ones, because symbols repeat across groups. The merge in
`useWindowReturns` even dedupes with `points.length > merged[sym].length`, so the code already
knows it's receiving the same series twice — and the hook takes `symbols` as a parameter and then
ignores it for fetching. **Fix:** add a `GET /sparklines?symbols=…&period=` sibling to the existing
`/indicators?symbols=` batch endpoint and fetch once. Nine requests → one, ~75 KB → ~67 KB, and it
fixes (c) below for free.

**b · Toggling Group ↔ Thesis refetches all 84 indicator snapshots.** `keys.indicators(symbols)`
keys on the symbol array; thesis mode adds thesis-only assets to the roster, so the array differs,
the key differs, and the whole batch misses cache. **Fix:** key on a stable union roster (every
symbol in any group *or* thesis, sorted) regardless of the active grouping, so the toggle is free.

**c · Thesis-only assets get no window returns.** In thesis mode the roster includes assets known
only through a thesis, but `series` is built purely from *group* sparklines — so those symbols get
`null` for 1wk/2wk/1mo, and the tooltip shows three em dashes that read as missing data rather than
never-fetched. Latent unless you actually have thesis-only assets; fixed automatically by (a).

**d · `useTheses()` runs unconditionally**, including in Group mode where it's only needed for the
roster fallback. Small, but free to gate.

Not a bug, worth stating so nobody "optimises" it: **paging cannot reduce fetching.** `span` in
`board.tsx` is computed over `sections.flatMap(...)` across every page, and the coverage pill counts
the whole roster — both need all 84. Page 2 costs nothing because page 1 already paid for
everything. The pager is a rendering device, not a loading one.

### Sustained cost

The SSE stream is well-behaved. `_poll_interval` gives 15 s while any venue is open, 60 s when only
pre/post are active, 300 s when everything is closed, and it sleeps to the next opening bell rather
than waking every five minutes past it. Quote pushes are deltas — only symbols whose values changed.

One thing to **measure rather than assume**: the `intraday` SSE event pushes the full bar set for
every grouped asset on its first iteration (`if not last_intraday_ts: intraday_payload = all_bars`).
If those are 1-minute bars for 84 symbols, that single frame is plausibly the largest thing that
crosses the wire all session. Deltas after it are small. Worth logging the byte size of the first
`intraday` frame before deciding whether it needs windowing.

---

## Out of scope / already rejected

- **Explaining σ in the tooltip.** An earlier draft carried "+0.9σ, because a typical day here is
  ±2.7%", sourced from `vnr_sigma` (already in the snapshot, already read by `computeLiveVnr`).
  Cut: it was the only prose sentence in a card of labels and numbers, and it explains a metric to
  the person who designed it. The vol scale as a plain `typical day ±2.7%` row was also tried and
  cut. If it ever comes back, it comes back as a figure, not a sentence.
- **Per-reason copy for feed-behind and session-gap.** See §3.
- **Fetching anything on hover.** The tooltip is free by construction; keep it that way.
- **Keeping `sunrise`/`sunset` and just enlarging them.** The glyphs are ~93% identical; size
  doesn't fix a shared silhouette.
```
