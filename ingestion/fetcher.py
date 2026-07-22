"""Fetch OHLCV data from Yahoo Finance via yfinance."""

import os
import sys
from datetime import date, timedelta
from typing import Any

import certifi

# curl_cffi cannot verify Yahoo TLS on many Windows installs; requests + certifi does.
_ca_bundle = certifi.where()
os.environ.setdefault("SSL_CERT_FILE", _ca_bundle)
os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle)
os.environ.setdefault("CURL_CA_BUNDLE", _ca_bundle)
if sys.platform == "win32":
    os.environ.setdefault("YF_DISABLE_CURL_CFFI", "1")

import pandas as pd
import yfinance as yf


def fetch_daily_prices_range(
    ticker: str,
    start: date,
    end: date | None = None,
) -> list[dict[str, Any]]:
    """Return daily OHLCV rows for [start, end)."""
    fetch_end = end or (date.today() + timedelta(days=1))

    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=fetch_end.isoformat(),
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


def fetch_initial_backfill(ticker: str, years: int) -> list[dict[str, Any]]:
    """Fetch full history for a ticker's first ingestion run."""
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=years * 365)
    return fetch_daily_prices_range(ticker, start, end)


def fetch_incremental(ticker: str, since: date) -> list[dict[str, Any]]:
    """Fetch only rows newer than the last stored date."""
    start = since + timedelta(days=1)
    end = date.today() + timedelta(days=1)
    if start >= end:
        return []
    return fetch_daily_prices_range(ticker, start, end)


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
