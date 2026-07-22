"""Prophet baseline model training, evaluation, and forecasting."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import mlflow
import pandas as pd
from prophet import Prophet
from sqlalchemy.engine import Engine

from config import (
    FORECAST_HORIZON_DAYS,
    MLFLOW_TRACKING_URI,
    PROPHET_INTERVAL_WIDTH,
    TRAIN_TEST_SPLIT,
)
from db import get_close_prices, insert_forecasts
from evaluate import evaluate_close_predictions

logger = logging.getLogger(__name__)


def _to_prophet_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return pd.DataFrame(
        {
            "ds": pd.to_datetime(df["date"]),
            "y": df["close"].astype(float),
        }
    )


def _split_prophet_frame(
    frame: pd.DataFrame,
    train_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_idx = int(len(frame) * train_fraction)
    if split_idx < 1 or split_idx >= len(frame):
        raise ValueError("Prophet train/test split produced empty partition")
    return frame.iloc[:split_idx].copy(), frame.iloc[split_idx:].copy()


def _build_prophet() -> Prophet:
    return Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=PROPHET_INTERVAL_WIDTH,
    )


def _evaluate_prophet(model: Prophet, test_frame: pd.DataFrame) -> dict[str, float]:
    future = test_frame[["ds"]].copy()
    forecast = model.predict(future)
    prior_close = test_frame["y"].shift(1).fillna(test_frame["y"].iloc[0]).to_numpy()
    actual_close = test_frame["y"].to_numpy()
    predicted_close = forecast["yhat"].to_numpy()
    return evaluate_close_predictions(actual_close, predicted_close, prior_close)


def _future_trading_days(last_date: date, horizon: int) -> list[date]:
    start = pd.Timestamp(last_date) + pd.tseries.offsets.BDay(1)
    dates = pd.bdate_range(start=start, periods=horizon)
    return [d.date() for d in dates]


def _register_model(model_name: str, run_id: str) -> None:
    client = mlflow.tracking.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    latest = max((int(v.version) for v in versions), default=0)
    if latest == 0:
        return
    client.transition_model_version_stage(
        name=model_name,
        version=str(latest),
        stage="Production",
        archive_existing_versions=True,
    )


def train_baseline(
    engine: Engine,
    ticker: str,
    run_date: date | None = None,
) -> dict[str, Any]:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    run_date = run_date or date.today()

    rows = get_close_prices(engine, ticker)
    if len(rows) < 60:
        raise ValueError(f"Insufficient price history for {ticker}")

    frame = _to_prophet_frame(rows)
    train_frame, test_frame = _split_prophet_frame(frame, TRAIN_TEST_SPLIT)

    eval_model = _build_prophet()
    eval_model.fit(train_frame)
    metrics = _evaluate_prophet(eval_model, test_frame)

    production_model = _build_prophet()
    production_model.fit(frame)

    last_date = pd.to_datetime(rows[-1]["date"]).date()
    future_dates = _future_trading_days(last_date, FORECAST_HORIZON_DAYS)
    future = pd.DataFrame({"ds": pd.to_datetime(future_dates)})
    forecast = production_model.predict(future)

    model_name = f"{ticker}_baseline"
    with mlflow.start_run(run_name=f"{ticker}_baseline") as run:
        mlflow.log_params(
            {
                "ticker": ticker,
                "model_type": "baseline",
                "horizon_days": FORECAST_HORIZON_DAYS,
                "interval_width": PROPHET_INTERVAL_WIDTH,
                "train_test_split": TRAIN_TEST_SPLIT,
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.prophet.log_model(
            production_model,
            artifact_path="model",
            registered_model_name=model_name,
        )
        run_id = run.info.run_id

    _register_model(model_name, run_id)

    forecast_rows = [
        {
            "ticker": ticker,
            "run_date": run_date,
            "target_date": target_date,
            "model_type": "baseline",
            "mlflow_run_id": run_id,
            "predicted_close": float(row["yhat"]),
            "confidence_lower": float(row["yhat_lower"]),
            "confidence_upper": float(row["yhat_upper"]),
        }
        for target_date, (_, row) in zip(future_dates, forecast.iterrows())
    ]
    insert_forecasts(engine, forecast_rows)

    logger.info(
        "Baseline training complete for %s (MAE=%.4f, RMSE=%.4f, dir_acc=%.2f%%)",
        ticker,
        metrics["mae"],
        metrics["rmse"],
        metrics["directional_accuracy"] * 100,
    )
    return {
        "ticker": ticker,
        "model_type": "baseline",
        "run_id": run_id,
        "metrics": metrics,
        "forecast_dates": future_dates,
    }
