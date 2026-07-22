#!/usr/bin/env python3
"""Train baseline (Prophet) and ML (XGBoost) models for stock tickers."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from config import DATABASE_URL, MLFLOW_TRACKING_URI, TICKERS_CONFIG_PATH
from db import get_engine
from train_baseline import train_baseline
from train_ml import train_ml

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


def train_ticker(engine, ticker: str, model: str) -> list[dict]:
    results: list[dict] = []

    if model in ("baseline", "both"):
        results.append(train_baseline(engine, ticker))

    if model in ("ml", "both"):
        results.append(train_ml(engine, ticker))

    return results


def run() -> int:
    parser = argparse.ArgumentParser(description="Train stock forecasting models")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", help="Single ticker symbol to train")
    group.add_argument("--all", action="store_true", help="Train all configured tickers")
    parser.add_argument(
        "--model",
        choices=["baseline", "ml", "both"],
        default="both",
        help="Which model(s) to train (default: both)",
    )
    args = parser.parse_args()

    logger.info("MLflow tracking URI: %s", MLFLOW_TRACKING_URI)

    tickers = load_tickers(TICKERS_CONFIG_PATH) if args.all else [args.ticker.upper()]
    engine = get_engine(DATABASE_URL)

    successes = 0
    failures = 0

    for ticker in tickers:
        try:
            results = train_ticker(engine, ticker, args.model)
            for result in results:
                metrics = result["metrics"]
                logger.info(
                    "%s %s complete — MAE=%.4f RMSE=%.4f dir_acc=%.1f%% forecasts=%s",
                    ticker,
                    result["model_type"],
                    metrics["mae"],
                    metrics["rmse"],
                    metrics["directional_accuracy"] * 100,
                    result["forecast_dates"],
                )
            successes += 1
        except Exception:
            failures += 1
            logger.exception("Training failed for %s", ticker)

    logger.info("Training complete: %s succeeded, %s failed", successes, failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
