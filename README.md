# stock-prediction

System to predict stock prices based on historical data.

## Data ingestion

Fetches daily OHLCV data from Yahoo Finance for configured tickers and stores it in Supabase (Postgres).

### Prerequisites

1. A Supabase project with the database schema applied — run `sql/schema.sql` in the Supabase SQL editor.
2. Your Supabase Postgres connection string (see `.env.example`).

### Configuration

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `DATABASE_URL` | Yes | — | Supabase Postgres URI |
| `INGESTION_LOOKBACK_DAYS` | No | `30` | Calendar days of history to fetch each run |
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
- `ingestion_log` — per-ticker success/failure and row counts
