"""Configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_TICKERS_PATH = (
    Path(__file__).resolve().parent.parent / "ingestion" / "config" / "tickers.yaml"
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
FORECAST_HORIZON_DAYS = int(os.environ.get("FORECAST_HORIZON_DAYS", "7"))
TRAIN_TEST_SPLIT = float(os.environ.get("TRAIN_TEST_SPLIT", "0.8"))
PROPHET_INTERVAL_WIDTH = float(os.environ.get("PROPHET_INTERVAL_WIDTH", "0.80"))
TICKERS_CONFIG_PATH = Path(os.environ.get("TICKERS_CONFIG_PATH", str(DEFAULT_TICKERS_PATH)))

MIN_TRAINING_ROWS = int(os.environ.get("MIN_TRAINING_ROWS", "60"))
