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

### What gets stored (ingestion)

- `stocks` — ticker registry (auto-created on first ingest)
- `daily_prices` — OHLCV rows, upserted by `(ticker, date)`
- `indicators` — SMA (20/50), EMA (20), RSI (14), MACD + signal, Bollinger Bands, 20-day volatility
- `ingestion_log` — per-ticker success/failure and row counts

## Model training

Trains a **Prophet baseline** and **quantile XGBoost ML** model per ticker, logs experiments to MLflow, registers production models, and writes 7-day forecasts to the `forecasts` table.

### Prerequisites

1. Ingestion has run and populated `daily_prices` and `indicators` for your tickers.
2. MLflow tracking server is running.

### Configuration

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `MLFLOW_TRACKING_URI` | No | `http://localhost:5000` | MLflow tracking server |
| `FORECAST_HORIZON_DAYS` | No | `7` | Trading days to forecast ahead |
| `TRAIN_TEST_SPLIT` | No | `0.8` | Chronological train fraction for holdout eval |
| `PROPHET_INTERVAL_WIDTH` | No | `0.80` | Prophet 80% prediction interval |
| `MIN_TRAINING_ROWS` | No | `60` | Minimum rows after indicator/lag warmup |

### Models

- **Baseline (`baseline`):** Facebook Prophet on daily close prices. Confidence bands come from Prophet's native prediction intervals.
- **ML (`ml`):** Three XGBoost quantile regressors (10th / 50th / 90th percentile) trained on engineered features to predict next-day return. The 7-day forecast is built iteratively; persisted indicators (RSI, MACD, etc.) are carried forward on future days while price-based lags are refreshed each step.

### Feature engineering (training-time)

Joined from `daily_prices` + `indicators`, plus derived features:

- Lagged returns (1, 5, 10 day)
- Volume change
- Day of week, month

These derived features are computed at training/forecast time and are not stored in the database.

### Run locally (one-off)

Prophet requires CmdStan; **Docker is recommended on Windows**. For local runs:

```bash
cd models
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
docker compose up mlflow -d   # from project root
python train.py --ticker AAPL --model both
```

### Run with Docker

```bash
docker compose up mlflow -d
docker compose --profile train run --rm models python train.py --ticker AAPL --model both
docker compose --profile train run --rm models python train.py --all --model both
```

Inside Docker, `MLFLOW_TRACKING_URI` defaults to `http://mlflow:5000`.

### What gets stored

- **MLflow:** parameters, metrics (MAE, RMSE, directional accuracy), and serialized models per run
- **Model Registry:** `{TICKER}_baseline` and `{TICKER}_ml` promoted to Production
- **`forecasts`:** 7 rows per model per training run (`predicted_close`, `confidence_lower`, `confidence_upper`)

Optional index for faster forecast lookups:

```sql
CREATE INDEX IF NOT EXISTS idx_forecasts_ticker_run
  ON forecasts (ticker, run_date DESC, model_type);
```

### Verification

1. Open MLflow UI at `http://localhost:5000` — confirm runs and registered models.
2. Query Supabase: `SELECT * FROM forecasts WHERE ticker = 'AAPL' ORDER BY run_date DESC, target_date;`
3. Expect 7 baseline + 7 ML rows per training run.
