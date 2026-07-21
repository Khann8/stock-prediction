#!/usr/bin/env python3
"""Ingest recent Yahoo Finance OHLCV data into Supabase Postgres."""

import logging
import sys
from pathlib import Path

import yaml

from config import DATABASE_URL, INGESTION_LOOKBACK_DAYS, TICKERS_CONFIG_PATH
from db import ensure_stock, get_engine, log_ingestion, upsert_daily_prices
from fetcher import fetch_daily_prices

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


def ingest_ticker(engine, ticker: str, lookback_days: int) -> tuple[str, int]:
    ensure_stock(engine, ticker)
    rows = fetch_daily_prices(ticker, lookback_days)
    count = upsert_daily_prices(engine, rows)
    log_ingestion(engine, ticker, "success", count)
    return ticker, count


def run() -> int:
    logger.info(
        "Starting ingestion (lookback_days=%s, config=%s)",
        INGESTION_LOOKBACK_DAYS,
        TICKERS_CONFIG_PATH,
    )

    tickers = load_tickers(TICKERS_CONFIG_PATH)
    engine = get_engine(DATABASE_URL)

    successes = 0
    failures = 0

    for ticker in tickers:
        try:
            _, count = ingest_ticker(engine, ticker, INGESTION_LOOKBACK_DAYS)
            logger.info("Ingested %s rows for %s", count, ticker)
            successes += 1
        except Exception as exc:
            failures += 1
            logger.exception("Failed to ingest %s", ticker)
            log_ingestion(engine, ticker, "failed", 0, str(exc))

    logger.info("Ingestion complete: %s succeeded, %s failed", successes, failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
