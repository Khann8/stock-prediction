"""Database helpers for Supabase Postgres via SQLAlchemy."""

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
