-- Stock forecasting system schema (run once in Supabase SQL editor)

CREATE TABLE IF NOT EXISTS stocks (
    ticker      TEXT PRIMARY KEY,
    name        TEXT,
    sector      TEXT,
    added_at    TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    ticker      TEXT REFERENCES stocks(ticker),
    date        DATE NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    adj_close   NUMERIC,
    volume      BIGINT,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS indicators (
    ticker        TEXT REFERENCES stocks(ticker),
    date          DATE NOT NULL,
    sma_20        NUMERIC,
    sma_50        NUMERIC,
    ema_20        NUMERIC,
    rsi_14        NUMERIC,
    macd          NUMERIC,
    macd_signal   NUMERIC,
    bb_upper      NUMERIC,
    bb_lower      NUMERIC,
    volatility_20 NUMERIC,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS forecasts (
    id                SERIAL PRIMARY KEY,
    ticker            TEXT REFERENCES stocks(ticker),
    run_date          DATE NOT NULL,
    target_date       DATE NOT NULL,
    model_type        TEXT NOT NULL,
    mlflow_run_id     TEXT,
    predicted_close   NUMERIC,
    confidence_lower  NUMERIC,
    confidence_upper  NUMERIC,
    created_at        TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id            SERIAL PRIMARY KEY,
    ticker        TEXT,
    run_at        TIMESTAMP DEFAULT now(),
    status        TEXT,
    rows_ingested INTEGER,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices (ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_run_at ON ingestion_log (run_at DESC);
