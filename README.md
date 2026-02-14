# fibenchi

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self-hosted investment research dashboard for tracking stocks, ETFs, and custom baskets. View OHLCV candlestick charts with technical indicators, write investment theses, annotate charts, and build pseudo-ETFs with equal-weight allocation.

## Features

- **Watchlist** — Track stocks and ETFs by ticker symbol, auto-validated against Yahoo Finance
- **Price charts** — Candlestick charts with RSI, SMA 20/50, Bollinger Bands, and MACD via [lightweight-charts](https://github.com/nicehash/lightweight-charts)
- **Real-time quotes** — Server-sent events push live prices with adaptive polling (15s during market hours, slower outside)
- **Technical indicators** — Per-asset indicator snapshots with color-coded cells
- **Pseudo-ETFs** — Create custom baskets of assets with equal-weight allocation, quarterly rebalancing, and indexed performance tracking
- **Investment thesis** — Markdown-formatted notes per asset or pseudo-ETF
- **Chart annotations** — Dated, colored markers on price charts
- **Groups & tags** — Organize assets into named collections and colored labels
- **Portfolio overview** — Composite equal-weight index of all watchlisted assets, top/bottom performer rankings
- **ETF holdings** — Drill into ETF constituents with per-holding indicator snapshots
- **Dark mode** — Toggle between light and dark themes

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
│       ├── models/        # SQLAlchemy models
│       ├── schemas/        # Pydantic request/response models
│       ├── routers/        # FastAPI route handlers
│       ├── services/       # Yahoo Finance integration, price sync, indicators
│       └── main.py         # App entrypoint, scheduler, SPA serving
├── frontend/
│   └── src/
│       ├── components/     # React components (charts, layout, shared UI)
│       ├── pages/          # Route pages
│       ├── lib/            # API client, React Query hooks, SSE quote stream
│       └── hooks/          # Custom React hooks
├── docker-compose.yaml     # Dev environment
├── docker-compose.prod.yaml
├── Dockerfile              # Multi-stage production build
└── .github/workflows/      # CI: test + build + push to GHCR
```
