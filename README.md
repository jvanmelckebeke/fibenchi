# fibenchi

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self-hosted investment research dashboard for tracking stocks, ETFs, and custom baskets. View OHLCV candlestick charts with technical indicators, write investment theses, annotate charts, and build pseudo-ETFs with equal-weight allocation.

## Features

- **Groups** — Organize assets into named groups with card or table view, sortable by any indicator, with configurable column visibility
- **Price charts** — Candlestick or line charts with overlay indicators (SMA 20/50, Bollinger Bands) and sub-charts (RSI, MACD) via [lightweight-charts](https://github.com/tradingview/lightweight-charts)
- **Technical indicators** — RSI, SMA, EMA, Bollinger Bands, MACD, ATR, ADX with color-coded thresholds and expandable per-asset charts in table rows
- **Real-time quotes** — Server-sent events push live prices with adaptive polling (15s market hours, 60s pre/post, 300s closed) and automatic reconnection with exponential backoff
- **Pseudo-ETFs** — Custom baskets with equal-weight allocation, quarterly rebalancing, indexed performance tracking, and synced crosshairs across constituent charts
- **Portfolio overview** — Composite equal-weight index of all tracked assets with dynamic entry (filters penny stocks), top/bottom performer rankings
- **ETF holdings** — Drill into ETF constituents with per-holding indicator snapshots and expandable charts
- **Investment thesis** — Markdown-formatted notes per asset or pseudo-ETF
- **Chart annotations** — Dated, colored markers on price charts
- **Tags** — Colored labels for categorizing assets within groups
- **Global search** — Cmd+K search across tracked assets and Yahoo Finance symbol lookup
- **Collapsible sidebar** — Navigation with group quick-access and inline group creation
- **Settings** — Configurable chart type, default period, indicator visibility, compact mode, decimal places, theme (dark/light/system)
- **Dark mode** — Toggle between light, dark, and system themes

## Tech Stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL, APScheduler |
| Frontend | React 19, TypeScript, TanStack React Query, Tailwind CSS, shadcn/ui |
| Charts   | lightweight-charts v5 |
| Data     | Yahoo Finance via yahooquery |
| Infra    | Docker Compose, GitHub Actions CI/CD, GHCR |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jvanmelckebeke/fibenchi.git
cd fibenchi

# Copy environment config (defaults work out of the box)
cp .env.example .env

# Start all services
docker compose up -d
```

The app will be available at:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:18000/api
- **API docs:** http://localhost:18000/docs

## Production

A multi-stage Dockerfile builds the React SPA and bundles it into the Python image, which serves both the API and frontend:

```bash
docker compose -f docker-compose.prod.yaml up -d
```

This exposes the app on port `18000`. Pre-built images are published to GHCR on every merge to `main`.

> **Security note:** The API has no built-in authentication. Deploy behind a reverse proxy (Traefik, nginx, Caddy) or VPN when exposing to a network. Change the default database credentials in production by setting `DATABASE_URL` in your `.env`.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://fibenchi:fibenchi@db:5432/fibenchi` | PostgreSQL connection string |
| `REFRESH_CRON` | `0 23 * * *` | Cron schedule for daily price sync |

## Development

The dev stack uses Docker Compose with hot reload for both backend (uvicorn `--reload`) and frontend (Vite HMR):

```bash
docker compose up -d              # Start all services
docker compose logs -f frontend   # Watch frontend logs
docker compose restart backend    # Restart after backend changes
```

### Running Tests

```bash
# Backend tests (uses SQLite in-memory, no DB needed)
docker compose exec backend pytest

# Single test
docker compose exec backend pytest tests/test_assets.py -k test_name

# Frontend lint + type check
docker compose exec frontend pnpm run lint
docker compose exec frontend pnpm run build
```

## Project Structure

```
fibenchi/
├── backend/
│   └── app/
│       ├── models/            # SQLAlchemy models
│       ├── schemas/           # Pydantic request/response models
│       ├── routers/           # FastAPI route handlers
│       ├── services/
│       │   ├── compute/       # Indicator math, group batching, portfolio/pseudo-ETF perf
│       │   ├── yahoo.py       # Yahoo Finance integration
│       │   ├── price_sync.py  # Price upsert logic
│       │   └── price_service.py  # Price fetch orchestration
│       └── main.py            # App entrypoint, scheduler, SPA serving
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chart/         # Chart builders, sync providers, sub-charts, legends
│       │   ├── ui/            # shadcn/radix primitives
│       │   └── ...            # Shared components (layout, search, tables, grids)
│       ├── pages/             # Route pages
│       ├── lib/               # API client, React Query hooks, SSE stream, settings, format utils
│       └── hooks/             # Shared React hooks (chart lifecycle, debounce, etc.)
├── docker-compose.yaml        # Dev environment
├── docker-compose.prod.yaml
├── Dockerfile                 # Multi-stage production build
└── .github/workflows/         # CI: test + build + push to GHCR
```
