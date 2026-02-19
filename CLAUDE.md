# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

The entire stack runs via Docker Compose:

```bash
docker compose up -d          # Start all services (db, backend, frontend)
docker compose restart backend  # Restart backend after code changes
docker compose logs frontend --tail 20  # Check frontend HMR/build errors
```

| Service  | Internal Port | Exposed Port | Tech                              |
|----------|--------------|--------------|-----------------------------------|
| db       | 5432         | 5432         | PostgreSQL 16                     |
| backend  | 8000         | 18000        | FastAPI + uvicorn (auto-reload)   |
| frontend | 5173         | 5173         | Vite dev server (HMR)             |

The Vite dev server proxies `/api/*` to the backend container.

**Production** uses a separate compose file (`docker-compose.prod.yaml`) and the root `Dockerfile` (multi-stage: Node builds the SPA into `static/`, Python serves it via FastAPI's SPA fallback). Don't run both stacks simultaneously — they share port 18000.

## Commands

**Backend** (run inside container: `docker compose exec backend <cmd>`):
```bash
pytest                            # Run all tests
pytest tests/test_assets.py -k test_name  # Single test
```

**Frontend** (run inside container: `docker compose exec frontend <cmd>`):
```bash
pnpm run lint                     # ESLint
pnpm run build                    # TypeScript check + Vite build
```

**CI** (`.github/workflows/ci.yaml`): runs `pytest` (backend), `pnpm lint` + `pnpm build` (frontend), then builds/pushes a Docker image to GHCR. Push to `main` tags `latest`, push to `dev` tags `dev`.

## Branching Strategy

Two long-lived branches: `main` (production, `fibenchi:latest`) and `dev` (staging, `fibenchi:dev`).

**For larger or risky changes** (schema migrations, multi-file refactors, new features that touch core logic): **always ask the user whether to PR into `dev` instead of `main`**. These changes can break the running production instance, so they should be validated on `dev` first. The flow is: feature branch → PR to `dev` → test on dev environment → PR `dev` into `main`.

**For small, safe changes** (docs, CI tweaks, single-file fixes with passing tests): PR directly to `main` is fine, but `dev` must be kept in sync afterward.

**Sync rules:**
- **Before starting work on `dev`**: always sync dev with main first (`git checkout dev && git merge origin/main`). Dev should never be behind main.
- `dev` updates → `main` only gets updated via PR (never force-push or direct merge)
- After merging a small fix directly to `main`, sync `dev` before any further dev-branch work.

## Architecture

**Backend:** FastAPI (async) → SQLAlchemy async ORM → PostgreSQL via asyncpg. APScheduler runs a daily price sync cron (configurable via `REFRESH_CRON` env var, default `0 23 * * *`).

**Frontend:** React 19 + TypeScript → TanStack React Query for server state → lightweight-charts v5 for charting. Styled with Tailwind CSS + shadcn/ui components. Real-time quotes via SSE (`QuoteStreamProvider` in `main.tsx`).

### Backend Layout

- `models/` — SQLAlchemy declarative models with `Mapped[]` type hints. Asset has a `type` enum (stock/etf) and `watchlisted` bool.
- `schemas/` — Pydantic v2 request/response models with `from_attributes` config. All router endpoints use `response_model` for typed OpenAPI schemas.
- `routers/` — FastAPI routers, all prefixed under `/api`. Dependency-injected `AsyncSession` via `get_db()`. Period params use `PeriodType = Literal["1mo","3mo","6mo","1y","2y","5y"]` with `Query()` for automatic 422 validation.
- `services/yahoo.py` — Yahoo Finance integration via `yahooquery`. Fetches OHLCV history, validates symbols, detects asset types, fetches ETF holdings.
- `services/price_sync.py` — Upserts price data using PostgreSQL `ON CONFLICT DO UPDATE`.
- `services/price_service.py` — Orchestrates price fetching with `_ensure_warmup_prices` for indicator warmup.
- `services/compute/` — Computational logic, separated from I/O:
  - `indicators.py` — `INDICATOR_REGISTRY` dict mapping indicator IDs to `IndicatorDef` (func, params, output_fields, warmup_periods, snapshot_derived). Computes RSI, SMA, EMA, Bollinger Bands, MACD, ATR, ADX.
  - `group.py` — Batch indicator snapshots with in-memory `TTLCache` (600s). `compute_and_cache_indicators()` caches by `(symbols, latest_date, group_id)`.
  - `pseudo_etf.py` — Equal-weight performance with quarterly rebalancing. Two modes: `_calc_static` (all constituents from day 1) and `_calc_dynamic` (assets join when price ≥ threshold, prevents penny-stock distortion).
  - `portfolio.py` — Portfolio index using dynamic entry with `min_entry_price=10.0`.
  - `utils.py` — Shared `prices_to_df()` converting ORM objects to indexed DataFrame.
- `services/entity_lookups.py` — Canonical lookup helpers: `find_asset()` returns `None` (for ephemeral price fetches of untracked symbols like ETF holdings), `get_asset()`/`get_group()`/`get_pseudo_etf()` raise HTTP 404.
- `utils.py` — `async_threadable` decorator (wraps sync functions for `asyncio.to_thread`), `TTLCache` class.
- `constants.py` — `PERIOD_DAYS` (period string → calendar days), `WARMUP_DAYS` (derived from max indicator warmup periods).

### Frontend Layout

- `lib/api.ts` — Centralized typed API client. All fetch calls go through `request<T>()`. Types mirror backend Pydantic schemas. Content-Type header only set when body is present.
- `lib/queries.ts` — React Query hooks with `keys` factory for cache management. Two stale time tiers: `STALE_5MIN` (most queries) and `STALE_24H` (ETF holdings). `useInvalidatingMutation` helper auto-invalidates query keys on success.
- `lib/quote-stream.tsx` — SSE-backed `QuoteStreamProvider` with exponential backoff reconnection (1s→30s cap). `useQuotes()` returns `Record<string, Quote>`, `useQuoteStatus()` returns connection state (`"connecting" | "connected" | "reconnecting" | "disconnected"`).
- `lib/settings.tsx` — `SettingsProvider` with dual-persistence: loads from `localStorage` synchronously on mount, then async-merges from `/api/settings` (backend wins on conflict). `useSettings()` returns `{ settings, updateSettings }`.
- `lib/indicator-registry.ts` — Central indicator descriptor registry. Three placement types: `"overlay"` (SMA/BB on main chart), `"subchart"` (RSI/MACD below), `"card"` (ATR/ADX as stat cards). Key exports: `getOverlayDescriptors()`, `getSubChartDescriptors()`, `getCardDescriptors()`, `getHoldingSummaryDescriptors()`, `getAllSortableFields()`, `resolveThresholdColor()`, `resolveAdxColor()`, `isPriceDenominated()`.
- `lib/format.ts` — `formatPrice()`, `changeColor()`, `formatChangePct()`, `currencySymbol()`. Also `buildYahooFinanceUrl()` — note: the Yahoo study config strings contain invisible `\u200c` zero-width non-joiner characters that must not be removed.
- `lib/use-price-flash.ts` — `usePriceFlash(price)` hook triggers green/red background flash on price changes, returns `[priceRef, pctRef]`.
- `pages/` — Route pages. Asset detail page conditionally shows ETF holdings for etf-type assets.
- `components/price-chart.tsx` — Main chart component rendering candlestick + overlay series + sub-charts + indicator cards, all inside a `ChartSyncProvider`.
- `components/expanded-asset-chart.tsx` — Shared expanded-row chart used by both `GroupTable` (compact: side-by-side layout) and `HoldingsGrid` (stacked layout with strip charts).
- `components/chart/` — Chart sub-components: Bollinger Band fill primitive, chart legends, pseudo-ETF charts, indicator cards, crosshair sync providers.
- `components/ui/` — shadcn/radix primitives. ESLint `react-refresh/only-export-components` is disabled for this directory since shadcn legitimately exports variant functions.
- `hooks/` — Shared hooks: `useChartLifecycle` (ResizeObserver + theme + cleanup), `useDebouncedValue`, `useTrackedSymbols`.

### Provider Hierarchy

The provider nesting order in `main.tsx` matters:

```
QueryClientProvider (staleTime=30s, retry=1)
  └─ SettingsProvider        ← loads from localStorage, then merges from backend
      └─ QuoteStreamProvider ← SSE stream with reconnection
          └─ BrowserRouter
              └─ App
```

### Chart System

The charting layer has four architectural tiers:

1. **`chart-builders.ts`** — Pure factory functions (no React). `createMainChart()`, `createOverlays()`, `createSubChart()`, `setMainSeriesData()`, `setAllOverlayData()`, `setSubChartData()`, `addAnnotationMarkers()`. These read from the indicator registry to construct charts.

2. **`chart-utils.ts`** — Theming: `baseChartOptions(container, height)`, `useChartTheme()` (reactive, watches `MutationObserver` on `<html>` class), `getChartTheme()` (imperative snapshot). `STACK_COLORS` — 10-color palette for pseudo-ETF breakdown charts.

3. **`ChartSyncProvider`** — Per-asset sync group. Charts self-register via `useRegisterChart()`. Syncs visible time range and crosshair position across all registered charts. Exposes `useChartHoverValues()` (for legends) and `useChartData()` (prices + indicators).

4. **`CrosshairTimeSyncProvider`** — Opt-in pub/sub layer for synchronizing crosshair time across *multiple independent* `ChartSyncProvider` instances (e.g., expanded rows in pseudo-ETF holdings). Uses refs (not state) to avoid re-renders on every crosshair move.

### Backend Startup Sequence

On startup (`main.py` lifespan):
1. `load_currency_cache(db)` — populates in-memory currency lookup to avoid per-request DB hits
2. APScheduler starts with cron trigger from `REFRESH_CRON`
3. `scheduled_refresh()` job: `sync_all_prices` → `compute_and_cache_indicators` (pre-warms cache so first group page load is instant)

## Key Patterns

- **Watchlist decoupling:** Deleting an asset sets `watchlisted=false` instead of removing the row. This preserves pseudo-ETF constituent relationships. Dashboard filters by `watchlisted=true`.
- **Pseudo-ETFs:** User-created baskets with equal-weight allocation, quarterly rebalancing (months 1,4,7,10), separate thesis/annotations tables.
- **Generic components:** `ThesisEditor` and `AnnotationsList` accept data + callbacks as props, reused across asset detail and pseudo-ETF detail pages.
- **Price warmup:** Indicator endpoint fetches `WARMUP_DAYS` extra calendar days before the display period to warm up SMA50/Bollinger Bands. Derived from `max_warmup_periods * 2.3`.
- **SSE quote stream:** Backend pushes watchlisted quotes via SSE with adaptive intervals (15s during market hours, 60s pre/post, 300s closed). Frontend reconnects with exponential backoff (1s→30s) on disconnect.
- **Stale price animation:** Group table falls back to DB-cached indicator prices when no live SSE quote is available. During market hours, stale values show a pulsing opacity animation (`.stale-price` CSS class). Suppressed when `market_state` is `CLOSED` or `POSTMARKET`.
- **Price flash:** `usePriceFlash` hook triggers green/red background fade animation (1.8s) on price tick changes, using a reflow trick to restart CSS animations on repeated same-direction ticks.
- **SPA fallback:** In production, the root `Dockerfile` copies the built SPA into `static/`. `main.py` mounts it and serves `index.html` for all non-API, non-asset routes. In dev, this directory doesn't exist so the mount is skipped.

## Testing

Backend tests use **SQLite in-memory** (`sqlite+aiosqlite:///:memory:`) — no database service needed. The `conftest.py` overrides `get_db()` with a test session. Note: SQLite doesn't support `pg_insert` (PostgreSQL-specific `ON CONFLICT`), so tests that exercise upsert logic mock `_upsert_prices` instead.

Tests seed ~500 days of price data to avoid triggering Yahoo Finance sync (the backend auto-fetches if stored data is insufficient).

All test files use `pytestmark = pytest.mark.asyncio(loop_scope="function")` for async test discovery.

`test_holdings` makes real network calls to Yahoo Finance and may fail with DNS errors in isolated environments — this is a known limitation.

## Database

PostgreSQL with async SQLAlchemy. Schema is managed via **Alembic** migrations (`backend/alembic/`). `alembic upgrade head` runs automatically on container startup (before uvicorn). The initial migration (`0001`) is idempotent — it detects existing tables and skips creation, so it works for both fresh and pre-existing databases.

To create a new migration after model changes:
```bash
docker compose exec backend alembic revision --autogenerate -m "description"
```

DB credentials: `fibenchi/fibenchi@db:5432/fibenchi` (dev only).
