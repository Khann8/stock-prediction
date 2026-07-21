"""Compute technical indicators from daily price history."""

from typing import Any

import pandas as pd


def compute_indicators(price_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return indicator rows aligned with input price rows."""
    if not price_rows:
        return []

    df = pd.DataFrame(price_rows).sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)

    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["ema_20"] = close.ewm(span=20, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    df["bb_upper"] = sma_20 + 2 * std_20
    df["bb_lower"] = sma_20 - 2 * std_20

    returns = close.pct_change()
    df["volatility_20"] = returns.rolling(20).std()

    indicator_rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        indicator_rows.append(
            {
                "ticker": row["ticker"],
                "date": row["date"],
                "sma_20": _to_float(row["sma_20"]),
                "sma_50": _to_float(row["sma_50"]),
                "ema_20": _to_float(row["ema_20"]),
                "rsi_14": _to_float(row["rsi_14"]),
                "macd": _to_float(row["macd"]),
                "macd_signal": _to_float(row["macd_signal"]),
                "bb_upper": _to_float(row["bb_upper"]),
                "bb_lower": _to_float(row["bb_lower"]),
                "volatility_20": _to_float(row["volatility_20"]),
            }
        )

    return indicator_rows


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
