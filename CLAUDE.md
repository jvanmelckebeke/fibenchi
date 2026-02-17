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

**CI** (`.github/workflows/ci.yaml`): runs `pytest` (backend), `pnpm lint` + `pnpm build` (frontend), then builds/pushes a Docker image to GHCR on merge to main.

## Architecture

**Backend:** FastAPI (async) → SQLAlchemy async ORM → PostgreSQL via asyncpg. APScheduler runs a daily price sync cron (configurable via `REFRESH_CRON` env var, default `0 23 * * *`).

**Frontend:** React 19 + TypeScript → TanStack React Query for server state → lightweight-charts v5 for charting. Styled with Tailwind CSS + shadcn/ui components. Real-time quotes via SSE (`QuoteStreamProvider` in `main.tsx`).

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
- `lib/quote-stream.tsx` — SSE-backed `QuoteStreamProvider` context. The `useQuotes()` hook returns a `Record<string, Quote>` updated in real-time from the backend's `/api/quotes/stream` endpoint.
- `pages/` — Route pages. Asset detail page conditionally shows ETF holdings for etf-type assets.
- `components/price-chart.tsx` — Dual-chart component (candlestick + RSI/MACD) with synced crosshairs via `setCrosshairPosition`.
- `components/chart/` — Chart sub-components: Bollinger Band fill primitive, chart legends, pseudo-ETF charts.
- `components/ui/` — shadcn/radix primitives. ESLint `react-refresh/only-export-components` is disabled for this directory since shadcn legitimately exports variant functions.

## Key Patterns

- **Watchlist decoupling:** Deleting an asset sets `watchlisted=false` instead of removing the row. This preserves pseudo-ETF constituent relationships. Dashboard filters by `watchlisted=true`.
- **Pseudo-ETFs:** User-created baskets with equal-weight allocation, quarterly rebalancing, separate thesis/annotations tables.
- **Generic components:** `ThesisEditor` and `AnnotationsList` accept data + callbacks as props, reused across asset detail and pseudo-ETF detail pages.
- **Chart crosshair sync:** Both handlers call `setCrosshairPosition` on both charts (source + target) to snap y-axis to actual data values.
- **Price warmup:** Indicator endpoint fetches 80 extra calendar days before the display period to warm up SMA50/Bollinger Bands.
- **SSE quote stream:** Backend pushes watchlisted quotes via SSE with adaptive intervals (15s during market hours, 60s pre/post, 300s closed). Frontend consumes via `useQuotes()` context hook — no per-tab polling.
- **SPA fallback:** In production, the root `Dockerfile` copies the built SPA into `static/`. `main.py` mounts it and serves `index.html` for all non-API, non-asset routes. In dev, this directory doesn't exist so the mount is skipped.

## Testing

Backend tests use **SQLite in-memory** (`sqlite+aiosqlite:///:memory:`) — no database service needed. The `conftest.py` overrides `get_db()` with a test session. Note: SQLite doesn't support `pg_insert` (PostgreSQL-specific `ON CONFLICT`), so tests that exercise upsert logic mock `_upsert_prices` instead.

Tests seed ~500 days of price data to avoid triggering Yahoo Finance sync (the backend auto-fetches if stored data is insufficient).

`test_holdings` makes real network calls to Yahoo Finance and may fail with DNS errors in isolated environments — this is a known limitation.

## Database

PostgreSQL with async SQLAlchemy. Schema is managed via **Alembic** migrations (`backend/alembic/`). `alembic upgrade head` runs automatically on container startup (before uvicorn). The initial migration (`0001`) is idempotent — it detects existing tables and skips creation, so it works for both fresh and pre-existing databases.

To create a new migration after model changes:
```bash
docker compose exec backend alembic revision --autogenerate -m "description"
```

DB credentials: `fibenchi/fibenchi@db:5432/fibenchi` (dev only).
