#!/usr/bin/env python3
"""Ingest Yahoo Finance OHLCV data and technical indicators into Supabase."""

import logging
import sys
from datetime import timedelta
from pathlib import Path

import yaml

from config import (
    DATABASE_URL,
    INDICATOR_WARMUP_DAYS,
    INGESTION_INITIAL_BACKFILL_YEARS,
    TICKERS_CONFIG_PATH,
)
from db import (
    ensure_stock,
    get_daily_prices,
    get_engine,
    get_last_price_date,
    indicator_history_start,
    log_ingestion,
    upsert_daily_prices,
    upsert_indicators,
)
from fetcher import fetch_incremental, fetch_initial_backfill
from indicators import compute_indicators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_tickers(config_path: Path) -> list[str]:
    if not config_path.exists():
        raise FileNotFoundError(f"Tickers config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    tickers = data.get("tickers", [])
    if not tickers:
        raise ValueError(f"No tickers configured in {config_path}")

    return [str(ticker).upper() for ticker in tickers]


def refresh_indicators(
    engine,
    ticker: str,
    update_from,
    warmup_days: int,
) -> int:
    history_start = indicator_history_start(update_from, warmup_days)
    price_rows = get_daily_prices(engine, ticker, history_start)
    indicator_rows = compute_indicators(price_rows)
    rows_to_store = [row for row in indicator_rows if row["date"] >= update_from]
    return upsert_indicators(engine, rows_to_store)


def ingest_ticker(
    engine,
    ticker: str,
    backfill_years: int,
    warmup_days: int,
) -> tuple[int, int, str]:
    ensure_stock(engine, ticker)
    last_date = get_last_price_date(engine, ticker)

    if last_date is None:
        mode = "backfill"
        price_rows = fetch_initial_backfill(ticker, backfill_years)
        if not price_rows:
            raise ValueError(f"No price data returned for {ticker}")
        indicator_update_from = min(row["date"] for row in price_rows)
    else:
        mode = "incremental"
        price_rows = fetch_incremental(ticker, last_date)
        indicator_update_from = last_date + timedelta(days=1)

    price_count = upsert_daily_prices(engine, price_rows)

    if price_count == 0:
        logger.info("%s is already up to date (last date: %s)", ticker, last_date)
        log_ingestion(engine, ticker, "success", 0)
        return 0, 0, mode

    indicator_count = refresh_indicators(
        engine,
        ticker,
        indicator_update_from,
        warmup_days,
    )
    log_ingestion(engine, ticker, "success", price_count)
    return price_count, indicator_count, mode


def run() -> int:
    logger.info(
        "Starting ingestion (backfill_years=%s, config=%s)",
        INGESTION_INITIAL_BACKFILL_YEARS,
        TICKERS_CONFIG_PATH,
    )

    tickers = load_tickers(TICKERS_CONFIG_PATH)
    engine = get_engine(DATABASE_URL)

    successes = 0
    failures = 0

    for ticker in tickers:
        try:
            price_count, indicator_count, mode = ingest_ticker(
                engine,
                ticker,
                INGESTION_INITIAL_BACKFILL_YEARS,
                INDICATOR_WARMUP_DAYS,
            )
            logger.info(
                "Ingested %s price rows and %s indicator rows for %s (%s mode)",
                price_count,
                indicator_count,
                ticker,
                mode,
            )
            successes += 1
        except Exception as exc:
            failures += 1
            logger.exception("Failed to ingest %s", ticker)
            log_ingestion(engine, ticker, "failed", 0, str(exc))

    logger.info("Ingestion complete: %s succeeded, %s failed", successes, failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
