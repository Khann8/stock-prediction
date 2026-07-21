# stock-prediction

System to predict stock prices based on historical data.

## Data ingestion

Fetches daily OHLCV data from Yahoo Finance for configured tickers, computes technical indicators, and stores everything in Supabase (Postgres).

### Ingestion modes

- **First run (backfill):** fetches the last 3 years of daily prices for each ticker (configurable via `INGESTION_INITIAL_BACKFILL_YEARS`).
- **Subsequent runs (incremental):** fetches only new trading days since the last stored date and upserts them.

After each price update, indicators are recomputed for the affected date range using a warmup window of prior prices loaded from the database.

### Prerequisites

1. A Supabase project with the database schema applied — run `sql/schema.sql` in the Supabase SQL editor.
2. Your Supabase Postgres connection string (see `.env.example`).

### Configuration

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `DATABASE_URL` | Yes | — | Supabase Postgres URI |
| `INGESTION_INITIAL_BACKFILL_YEARS` | No | `3` | Years of history on first run per ticker |
| `INDICATOR_WARMUP_DAYS` | No | `90` | Prior days loaded for indicator recomputation |
| `TICKERS_CONFIG_PATH` | No | `ingestion/config/tickers.yaml` | Path to ticker list |
| `INGESTION_CRON` | No | `0 22 * * 1-5` | Cron schedule (Docker only) |
| `RUN_ON_STARTUP` | No | `true` | Run ingestion when container starts |

Edit `ingestion/config/tickers.yaml` to change which stocks are ingested:

```yaml
tickers:
  - AAPL
  - MSFT
```

### Run locally (one-off)

```bash
cd ingestion
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy ..\.env.example ..\.env  # then fill in DATABASE_URL
python run_ingestion.py
```

### Run with Docker

```bash
copy .env.example .env   # fill in DATABASE_URL
docker compose up --build ingestion
```

The container runs ingestion on startup, then on the configured cron schedule. Each ticker is processed independently — one failure does not stop the batch. Results are logged to the `ingestion_log` table.

### What gets stored

- `stocks` — ticker registry (auto-created on first ingest)
- `daily_prices` — OHLCV rows, upserted by `(ticker, date)`
- `indicators` — SMA (20/50), EMA (20), RSI (14), MACD + signal, Bollinger Bands, 20-day volatility
- `ingestion_log` — per-ticker success/failure and row counts
