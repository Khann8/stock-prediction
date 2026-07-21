"""Fetch OHLCV data from Yahoo Finance via yfinance."""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf


def fetch_daily_prices(ticker: str, lookback_days: int) -> list[dict[str, Any]]:
    """Return daily OHLCV rows for the last `lookback_days` calendar days."""
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=lookback_days)

    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        return []

    df = _normalize_columns(df)
    df = df.dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).date

    rows: list[dict[str, Any]] = []
    for row_date, row in df.iterrows():
        rows.append(
            {
                "ticker": ticker,
                "date": row_date,
                "open": _to_float(row.get("Open")),
                "high": _to_float(row.get("High")),
                "low": _to_float(row.get("Low")),
                "close": _to_float(row.get("Close")),
                "adj_close": _to_float(row.get("Adj Close")),
                "volume": _to_int(row.get("Volume")),
            }
        )

    return rows


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance multi-index columns when present."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
