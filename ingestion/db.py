"""Database helpers for Supabase Postgres via SQLAlchemy."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(database_url: str) -> Engine:
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(database_url, pool_pre_ping=True)


def ensure_stock(engine: Engine, ticker: str) -> None:
    stmt = text(
        """
        INSERT INTO stocks (ticker)
        VALUES (:ticker)
        ON CONFLICT (ticker) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"ticker": ticker})


def upsert_daily_prices(engine: Engine, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO daily_prices (
            ticker, date, open, high, low, close, adj_close, volume
        )
        VALUES (
            :ticker, :date, :open, :high, :low, :close, :adj_close, :volume
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume
        """
    )

    with engine.begin() as conn:
        conn.execute(stmt, rows)

    return len(rows)


def get_last_price_date(engine: Engine, ticker: str) -> date | None:
    stmt = text(
        """
        SELECT MAX(date) AS last_date
        FROM daily_prices
        WHERE ticker = :ticker
        """
    )
    with engine.connect() as conn:
        result = conn.execute(stmt, {"ticker": ticker}).mappings().one()
    return result["last_date"]


def get_daily_prices(
    engine: Engine,
    ticker: str,
    start_date: date,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    stmt = text(
        """
        SELECT ticker, date, close
        FROM daily_prices
        WHERE ticker = :ticker
          AND date >= :start_date
          AND (:end_date IS NULL OR date <= :end_date)
        ORDER BY date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            stmt,
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).mappings().all()

    return [dict(row) for row in rows]


def upsert_indicators(engine: Engine, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO indicators (
            ticker, date, sma_20, sma_50, ema_20, rsi_14,
            macd, macd_signal, bb_upper, bb_lower, volatility_20
        )
        VALUES (
            :ticker, :date, :sma_20, :sma_50, :ema_20, :rsi_14,
            :macd, :macd_signal, :bb_upper, :bb_lower, :volatility_20
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            sma_20 = EXCLUDED.sma_20,
            sma_50 = EXCLUDED.sma_50,
            ema_20 = EXCLUDED.ema_20,
            rsi_14 = EXCLUDED.rsi_14,
            macd = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            bb_upper = EXCLUDED.bb_upper,
            bb_lower = EXCLUDED.bb_lower,
            volatility_20 = EXCLUDED.volatility_20
        """
    )

    with engine.begin() as conn:
        conn.execute(stmt, rows)

    return len(rows)


def indicator_history_start(update_from: date, warmup_days: int) -> date:
    return update_from - timedelta(days=warmup_days)


def log_ingestion(
    engine: Engine,
    ticker: str,
    status: str,
    rows_ingested: int,
    error_message: str | None = None,
) -> None:
    stmt = text(
        """
        INSERT INTO ingestion_log (ticker, status, rows_ingested, error_message)
        VALUES (:ticker, :status, :rows_ingested, :error_message)
        """
    )
    with engine.begin() as conn:
        conn.execute(
            stmt,
            {
                "ticker": ticker,
                "status": status,
                "rows_ingested": rows_ingested,
                "error_message": error_message,
            },
        )
