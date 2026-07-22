"""Database helpers for model training and forecast persistence."""

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(database_url: str) -> Engine:
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(database_url, pool_pre_ping=True)


def get_training_data(engine: Engine, ticker: str) -> list[dict[str, Any]]:
    stmt = text(
        """
        SELECT
            dp.ticker,
            dp.date,
            dp.open,
            dp.high,
            dp.low,
            dp.close,
            dp.adj_close,
            dp.volume,
            i.sma_20,
            i.sma_50,
            i.ema_20,
            i.rsi_14,
            i.macd,
            i.macd_signal,
            i.bb_upper,
            i.bb_lower,
            i.volatility_20
        FROM daily_prices dp
        INNER JOIN indicators i
            ON dp.ticker = i.ticker AND dp.date = i.date
        WHERE dp.ticker = :ticker
        ORDER BY dp.date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, {"ticker": ticker}).mappings().all()
    return [dict(row) for row in rows]


def get_close_prices(engine: Engine, ticker: str) -> list[dict[str, Any]]:
    stmt = text(
        """
        SELECT ticker, date, close
        FROM daily_prices
        WHERE ticker = :ticker
        ORDER BY date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, {"ticker": ticker}).mappings().all()
    return [dict(row) for row in rows]


def insert_forecasts(engine: Engine, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO forecasts (
            ticker, run_date, target_date, model_type, mlflow_run_id,
            predicted_close, confidence_lower, confidence_upper
        )
        VALUES (
            :ticker, :run_date, :target_date, :model_type, :mlflow_run_id,
            :predicted_close, :confidence_lower, :confidence_upper
        )
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, rows)
    return len(rows)
