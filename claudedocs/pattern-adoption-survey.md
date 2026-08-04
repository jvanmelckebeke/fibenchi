# Pattern-adoption survey — where Symbol/Venue/session-exactness applies elsewhere

Date: 2026-08-04. Context: after #559 (σ-Move √N gap inflation, PRs #560/#561) we
introduced three patterns: `Symbol(str)` with ticker shape interpreted in one
place, `Venue` facade with traits-as-data (`EXTENDED_HOURS`), and session-exact
gap awareness replacing positional/heuristic time assumptions. Three parallel
codebase surveys looked for other application sites. Findings, ranked.

## A. Correctness bugs of the #559 class (session-exactness fixes real numbers)

1. **`_ewma_daily_vol` denominator still eats gap returns** —
   `backend/app/services/compute/indicators.py:131-144`. The vnr numerator is
   gap-guarded but the EWMA variance is built from unfiltered `pct_change()`: a
   3-session hole squares a √3-inflated return into the variance (λ=0.94 →
   ~11-day half-life), so σ is inflated for weeks after a gap and every
   subsequent σ-Move is **understated** — the app under-flags genuine events
   after a data outage, and nothing renders blank to warn. Also contaminates
   `vnr_sigma` → frontend `computeLiveVnr`. Fix: thread `gap_series` into
   `_ewma_daily_vol`, drop (not zero) gap-spanning returns. This is issue #559
   "fix 4", upgraded from minor to the top remaining item.

2. **`build_indicator_snapshot` `change_pct` is positional** —
   `indicators.py:598-606`. A multi-session return labelled "1-day change";
   it's the DB fallback the group table shows exactly when the live quote is
   absent (post-outage). Suppress/annotate using the last `gap_series` value.

3. **`_compute_deltas` positional diff** — `indicators.py:636-659`. Across a
   hole: fake ⚠ outlier badge on the gap bar (rsi_delta/macd_delta sigma), and
   the inflated |Δ| sits in the 20-row rolling std, suppressing genuine outlier
   flags for a month. Fix: NaN deltas where `gaps > 1` (rolling stats skip NaN).

4. **`price_heal` has no interior-hole detection** — `price_heal.py:38-105`
   only reconciles the trailing bar. `Symbol(sym).venue.session_dates(first,
   last)` minus stored dates = exact missing-session list;
   `sync_asset_prices_range` already exists to fill it. This would have
   auto-repaired the original IWDA incident. (Issue #559 "fix 3".) Needs
   negative-caching for holes Yahoo genuinely can't fill (reuse
   `_earliest_date_cache` idea) and the "trust data over calendar" rule.

5. **Frontend `weekdaysBetween` is holiday-blind** — `movement-stats.ts:42-52`.
   Backend gap guard is now venue-exact; the frontend copy still excludes the
   session after every exchange holiday from max daily gain/loss and
   up/down/session counts (~10 sessions/yr, disproportionately high-vol
   reopens). Fix without new computation: the asset-detail indicators already
   carry per-bar `vnr_gap_sessions` — read that instead, delete
   `weekdaysBetween`.

6. **`computeLiveVnr`/`isStoredVnrStale` infer session identity from price
   proximity** — `indicator-registry.ts:183,201-217,236-244`. 0.5% close-match
   proxy (duplicated constant with `price_sync.py:20`): flat multi-session
   stretch passes (wrong σ anchor), >0.5% overnight gap-up reads as stale
   (blanks σ-Move on the most interesting days). Proper fix: backend-computed
   `sessions_behind` int on the payload (Venue answers it definitionally);
   retires two heuristics + the duplicated tolerance. Cheap interim: gate
   `computeLiveVnr` on `vnr_gap_sessions == null` (currently only the DB
   branch checks it).

7. **`compute_performers` ranks assets over unaligned windows** —
   `portfolio.py:65-104` (same shape in `pseudo_etf.calculate_performance:57`).
   Calendar-day window start + first *stored* bar baseline → an asset with a
   leading hole or venue closure is measured over a shorter window and ranked
   head-to-head. Venue-exact "Nth session back" anchor, or flag materially
   late baselines.

## B. Heuristics the Venue schedule API replaces

1. **`intraday.py:20-69` `_EXCHANGE_HOURS` + `_classify_session`** — 27-entry
   hand-maintained tz→wall-clock table with ET fallback; wrong on half-days
   (post bars filed as regular), holiday-blind, no "closed" value. Strictly
   superseded by `Venue.phase()`. Needs a pre/regular/post ↔
   premarket/open/aftermarket/closed name map at the DB boundary and a decision
   for EU bars outside regular hours (currently pre/post, schedule says
   closed). Deletes ~50 lines of venue data.
2. **`main.py:155-188` `scheduled_intraday_sync`** — shuffles the portfolio and
   quotes 15 random symbols every 60s to guess "is anything open" (~80% miss
   chance for a 3-symbol Tokyo tail in a 200-symbol portfolio; 1,440 Yahoo
   round-trips/day). Replace with `any(venue.phase() != "closed")` over the
   portfolio's ~8 venues: deterministic, free, holiday-aware. Biggest
   cost-saving item.
3. **Weekend guards `main.py:130,157`** — `weekday() >= 5` skips crypto (24/7)
   all weekend and runs all day on global holidays; server-local date is wrong
   at tz edges (Monday 09:00 Tokyo = Sunday UTC). Same venue-phase one-liner.
4. **SSE interval selection `quote_service.py:126-131`** — live `market_state`
   only: empty quote batch during regular hours → 300s poll; all-closed →
   fixed 300s sleep can oversleep an open by ~5min. Backstop:
   `min(live_interval, schedule_interval)` + clamp sleep to `next_open`. Live
   feed may only speed polling, never a calendar bug slowing it.
5. **`drop_unsettled_last_bar` `price_sync.py:97-102`** — session-forming
   decision hinges solely on quote `market_state`; quote fetch failure → the
   unsettled bar gets stored (the state that blanks σ-Move). Backstop only when
   `market_state is None` with `venue.phase() == "open"`; never override (halts
   are the case where live beats schedule). High review cost — silent-data-loss
   failure mode, heavily tested function.
6. **Frontend `.stale-price` suppression is dead code** —
   `table-row.tsx:114-120`: suppression reads `quote.market_state`, but the
   flag only evaluates when there IS no quote → `isMarketClosed` is always
   false → every DB-fallback row pulses, including Sundays with SSE down.
   Needs a scheduled phase delivered to the client (field or tiny endpoint).
7. **Per-venue refresh scheduling** — `config.py:6` + `main.py:200-221`: 23:00
   UTC cron + hardcoded 8/16 UTC supplemental sweeps approximate "after each
   venue's close + publish lag". Venue `next_close() + lag` (lag = sibling data
   table to EXTENDED_HOURS) → N small per-venue syncs, no staleness window,
   half-day aware. **High effort** (dynamic APScheduler jobs, DST); only if
   per-venue staleness actually hurts.
8. **`intraday.py:16,145,175` ET-anchored cutoffs for all venues** — read
   window and cleanup boundaries wrong for Asian sessions; papered over by the
   generous 2-day window. Low priority.

## C. Consolidation: one venue table, one ticker parser

Four venue tables exist, none sharing keys:
`SUFFIX_CALENDARS` (suffix→calendar, 36) · `EXCHANGE_CURRENCY_MAP`
(`yahoo/currency.py:9-62`, suffix→currency, 55, includes suffixes the calendar
table lacks: .CO .AT .TA .SR .IC .IS .JK .BK .V .IL .TWO .QA) · euronext
provider `MARKET_SUFFIX` (`euronext.py:26-45`, display-name→suffix, the inverse
mapping) · `_EXCHANGE_HOURS` (intraday.py, tz→hours — deleted by B1).

Suffix *parsing* is implemented 3×: `Symbol.calendar_name`,
`currency_from_suffix` (`currency.py:65-74`), and the companion app's
`fromSuffix` (`fibenchi-app/lib/market/yahoo/currency.ts:89-93`, a hand-synced
copy of the backend table that will drift).

Plan: one venue table with columns (suffix, calendar, currency, display names);
`Venue` gains a `currency` trait; `Symbol.currency` replaces
`currency_from_suffix` (suffixes without a calendar keep currency-only
entries). Symbol construction sites (`euronext.py:142`, `xetra.py:85`
f-string suffix literals) get a `Symbol.from_venue`-style constructor. The
~25 scattered `.upper()` normalizations and the duplicated CSV parsing
(`quote_service.py:27`, `routers/data.py:55`) fold into Symbol helpers.
Companion-app duplication (currency table, YIELD_INDICES triplicate,
"is index/is crypto" answered 3 different ways across the 3 codebases) is a
candidate for the same schema-export treatment as CompanionConfig — later.

## D. Kind-conditionals → trait tables

- **`market_state` predicates: 6 sites, 5 different sets** —
  `quote_service.py:96,126,128`, `main.py:180` (verbatim copy of
  quote_service:96), `price_sync.py:26`, `table-row.tsx:119`; canonical 6-value
  list exists only as a docstring (`schemas/quote.py:13`). Fix: one
  `MARKET_STATES` trait table (`phase`, `active`, `session_forming`) — the
  `phase` field is the join key to `Venue.phase()`, which is what makes the B4/
  B5/B6 backstops one-liners. Frontend already has the right shape in
  `market-state.ts` (presentation-only today) — extend it. **This is the
  enabling change for most of section B.**
- **UI period label pairs** duplicated in `group-page.tsx:225-227` and
  `settings.tsx:92-94` — add `PERIOD_LABELS` beside `STANDARD_PERIODS`. Small.
- **`euronext.py:74-107` `_resolve_market`** — duplicated fallback block +
  two O(n) reverse scans; precompute one flat dict. Small, low priority.
- **Asset-type branches (`format.ts:69,123`, `price-chart.tsx:41`,
  `asset-detail/index.tsx:42`)** — verdict: skip. Dispersed one-liners at
  point of use, 3-value enum, not growing. Not worth a traits table.
- **Indicator descriptors (`indicator-descriptors.ts`)** — already the
  pattern done right; use as the template. Same for `PERIOD_DAYS` mirrors
  (network boundary, correctly commented) and Yahoo `PERIOD_MAP` (adapter,
  not a duplicate).

## Verified safe (checked, no action)

Chart builders/time maps (date-keyed joins, not positional); `thesis.py`
ffill-on-levels; rolling indicators consuming N rows (correct "last N
sessions" semantics; TR/EFI shift(1) transient is negligible);
`drop_unsettled_last_bar`'s iloc[-2] (identity check, not a return);
pseudo-ETF quarterly rebalance trigger (first-row-of-quarter semantics hold
across gaps). Pseudo-ETF cross-venue ffill understates dispersion on
one-venue holidays — inherent to a composite, now *detectable* via
`venue.is_session`, but probably acceptable.

## Suggested sequencing

1. **A1+A3 (+A2)** — finish the #559 family inside `compute_indicators` where
   `gap_series` already exists (one PR).
2. **A4** — interior-hole heal pass (one PR; auto-repairs future incidents).
3. **D-market-states table** — enabler (small PR).
4. **B2+B3 (+B4)** — scheduler gates + SSE backstop (one PR, immediate API-call
   savings).
5. **B1** — intraday phase classification via Venue (one PR).
6. **C** — venue-table consolidation + `Symbol.currency` (one PR).
7. Frontend session-identity items (A5, A6, B6) — gated on deciding how
   phase/`sessions_behind` reaches the client (one design, then small PRs).
8. B7 (per-venue cron) — only if staleness is an observed pain.
