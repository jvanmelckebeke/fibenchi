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

## Commands

**Backend** (run inside `fibenchi-backend-1` container or with `docker exec`):
```bash
pytest                            # Run all tests
pytest tests/test_assets.py -k test_name  # Single test
```

**Frontend** (run inside `fibenchi-frontend-1` container):
```bash
pnpm run lint                     # ESLint
pnpm run build                    # TypeScript check + Vite build
```

## Architecture

**Backend:** FastAPI (async) → SQLAlchemy async ORM → PostgreSQL via asyncpg. APScheduler runs a daily price sync cron at 23:00 UTC.

**Frontend:** React 19 + TypeScript → TanStack React Query for server state → lightweight-charts v5 for charting. Styled with Tailwind CSS + shadcn/ui components.

### Backend Layout

- `models/` — SQLAlchemy declarative models with `Mapped[]` type hints. Asset has a `type` enum (stock/etf) and `watchlisted` bool.
- `schemas/` — Pydantic v2 request/response models with `from_attributes` config.
- `routers/` — FastAPI routers, all prefixed under `/api`. Dependency-injected `AsyncSession` via `get_db()`.
- `services/yahoo.py` — Yahoo Finance integration via `yahooquery`. Fetches OHLCV history, validates symbols, detects asset types, fetches ETF holdings.
- `services/price_sync.py` — Upserts price data using PostgreSQL `ON CONFLICT DO UPDATE`.
- `services/indicators.py` — Computes RSI, SMA20/50, Bollinger Bands, MACD from price history.

### Frontend Layout

- `lib/api.ts` — Centralized typed API client. All fetch calls go through `request<T>()`. Types mirror backend Pydantic schemas.
- `lib/queries.ts` — React Query hooks with `keys` factory for cache management. Every API method has a corresponding `use*` hook.
- `pages/` — Route pages. Asset detail page conditionally shows ETF holdings for etf-type assets.
- `components/price-chart.tsx` — Dual-chart component (candlestick + RSI) with synced crosshairs via `setCrosshairPosition`.
- `components/ui/` — shadcn/radix primitives.

## Key Patterns

- **Watchlist decoupling:** Deleting an asset sets `watchlisted=false` instead of removing the row. This preserves pseudo-ETF constituent relationships. Dashboard filters by `watchlisted=true`.
- **Pseudo-ETFs:** User-created baskets with equal-weight allocation, quarterly rebalancing, separate thesis/annotations tables.
- **Generic components:** `ThesisEditor` and `AnnotationsList` accept data + callbacks as props, reused across asset detail and pseudo-ETF detail pages.
- **Chart crosshair sync:** Both handlers call `setCrosshairPosition` on both charts (source + target) to snap y-axis to actual data values.
- **Price warmup:** Indicator endpoint fetches 80 extra calendar days before the display period to warm up SMA50/Bollinger Bands.

## Database

PostgreSQL with async SQLAlchemy. Alembic is set up but schema changes are currently handled via `Base.metadata.create_all()` on startup plus `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in the lifespan function for incremental column additions.

DB credentials: `fibenchi/fibenchi@db:5432/fibenchi` (dev only).
