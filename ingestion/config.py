"""Configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_TICKERS_PATH = Path(__file__).parent / "config" / "tickers.yaml"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
INGESTION_INITIAL_BACKFILL_YEARS = int(
    os.environ.get("INGESTION_INITIAL_BACKFILL_YEARS", "3")
)
INDICATOR_WARMUP_DAYS = int(os.environ.get("INDICATOR_WARMUP_DAYS", "90"))
TICKERS_CONFIG_PATH = Path(os.environ.get("TICKERS_CONFIG_PATH", str(DEFAULT_TICKERS_PATH)))
