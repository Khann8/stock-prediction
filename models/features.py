"""Training-time feature engineering from prices and persisted indicators."""

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from config import MIN_TRAINING_ROWS, TRAIN_TEST_SPLIT
from db import get_training_data

PERSISTED_FEATURE_COLUMNS = [
    "sma_20",
    "sma_50",
    "ema_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "bb_upper",
    "bb_lower",
    "volatility_20",
    "close",
    "volume",
]

DERIVED_FEATURE_COLUMNS = [
    "return_lag_1",
    "return_lag_5",
    "return_lag_10",
    "volume_change",
    "day_of_week",
    "month",
]

FEATURE_COLUMNS = PERSISTED_FEATURE_COLUMNS + DERIVED_FEATURE_COLUMNS
TARGET_COLUMN = "next_day_return"


def load_training_frame(engine: Engine, ticker: str) -> pd.DataFrame:
    rows = get_training_data(engine, ticker)
    if not rows:
        raise ValueError(f"No training data found for {ticker}")

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return add_derived_features(df)


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    close = result["close"].astype(float)

    result["return_lag_1"] = close.pct_change(1).shift(1)
    result["return_lag_5"] = close.pct_change(5).shift(1)
    result["return_lag_10"] = close.pct_change(10).shift(1)
    result["volume_change"] = result["volume"].astype(float).pct_change()

    dates = pd.to_datetime(result["date"])
    result["day_of_week"] = dates.dt.dayofweek
    result["month"] = dates.dt.month

    result[TARGET_COLUMN] = close.shift(-1) / close - 1
    return result


def drop_incomplete_rows(df: pd.DataFrame) -> pd.DataFrame:
    required = FEATURE_COLUMNS + [TARGET_COLUMN]
    cleaned = df.dropna(subset=required).reset_index(drop=True)
    if len(cleaned) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Insufficient training rows after warmup ({len(cleaned)} < {MIN_TRAINING_ROWS})"
        )
    return cleaned


def chronological_split(
    df: pd.DataFrame,
    train_fraction: float = TRAIN_TEST_SPLIT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_idx = int(len(df) * train_fraction)
    if split_idx < 1 or split_idx >= len(df):
        raise ValueError("Train/test split produced empty train or test set")
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def prepare_xy(
    df: pd.DataFrame,
    train_fraction: float = TRAIN_TEST_SPLIT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, list[str]]:
    cleaned = drop_incomplete_rows(df)
    train_df, test_df = chronological_split(cleaned, train_fraction)

    feature_names = FEATURE_COLUMNS.copy()
    x_train = train_df[feature_names]
    y_train = train_df[TARGET_COLUMN]
    x_test = test_df[feature_names]
    y_test = test_df[TARGET_COLUMN]
    return x_train, x_test, y_train, y_test, feature_names


def build_forecast_seed(df: pd.DataFrame) -> pd.DataFrame:
    """Return cleaned history used to seed iterative multi-day forecasts."""
    return drop_incomplete_rows(df)


def append_forecast_row(
    history: pd.DataFrame,
    ticker: str,
    target_date: pd.Timestamp,
    close: float,
    volume: float | None = None,
) -> pd.DataFrame:
    """Append a synthetic row and recompute derived features."""
    last_row = history.iloc[-1]
    volume_value = float(volume if volume is not None else last_row["volume"])

    synthetic: dict[str, Any] = {
        "ticker": ticker,
        "date": target_date.date(),
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "adj_close": close,
        "volume": volume_value,
    }
    for column in PERSISTED_FEATURE_COLUMNS:
        if column in ("close", "volume"):
            continue
        synthetic[column] = last_row[column]

    extended = pd.concat(
        [history, pd.DataFrame([synthetic])],
        ignore_index=True,
    )
    return add_derived_features(extended)


def feature_vector_for_row(row: pd.Series, feature_names: list[str]) -> np.ndarray:
    return row[feature_names].astype(float).to_numpy()
