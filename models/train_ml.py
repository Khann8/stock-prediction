"""Quantile XGBoost ML model training, evaluation, and forecasting."""

from __future__ import annotations

import logging
import pickle
import tempfile
from datetime import date
from typing import Any

import mlflow
import pandas as pd
import xgboost as xgb
from sqlalchemy.engine import Engine

from config import FORECAST_HORIZON_DAYS, MLFLOW_TRACKING_URI, TRAIN_TEST_SPLIT
from db import insert_forecasts
from evaluate import evaluate_return_predictions
from features import (
    FEATURE_COLUMNS,
    append_forecast_row,
    build_forecast_seed,
    drop_incomplete_rows,
    feature_vector_for_row,
    load_training_frame,
    prepare_xy,
)

logger = logging.getLogger(__name__)

QUANTILES = (0.1, 0.5, 0.9)


def _xgb_params(quantile_alpha: float) -> dict[str, Any]:
    return {
        "objective": "reg:quantileerror",
        "quantile_alpha": quantile_alpha,
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1,
    }


def _train_quantile_models(
    x_train: pd.DataFrame,
    y_train: pd.Series,
) -> dict[float, xgb.XGBRegressor]:
    models: dict[float, xgb.XGBRegressor] = {}
    for quantile in QUANTILES:
        model = xgb.XGBRegressor(**_xgb_params(quantile))
        model.fit(x_train, y_train)
        models[quantile] = model
    return models


def _future_trading_days(last_date: date, horizon: int) -> list[date]:
    start = pd.Timestamp(last_date) + pd.tseries.offsets.BDay(1)
    dates = pd.bdate_range(start=start, periods=horizon)
    return [d.date() for d in dates]


def _register_model(model_name: str) -> None:
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


def _iterative_forecast(
    history: pd.DataFrame,
    models: dict[float, xgb.XGBRegressor],
    feature_names: list[str],
    ticker: str,
    horizon: int,
) -> list[dict[str, float | date]]:
    working_history = history.copy()
    last_date = pd.to_datetime(working_history.iloc[-1]["date"]).date()
    future_dates = _future_trading_days(last_date, horizon)

    forecasts: list[dict[str, float | date]] = []
    for target_date in future_dates:
        current_row = working_history.iloc[-1]
        features = feature_vector_for_row(current_row, feature_names).reshape(1, -1)

        predicted_returns = {
            quantile: float(models[quantile].predict(features)[0]) for quantile in QUANTILES
        }
        last_close = float(current_row["close"])
        predicted_closes = {
            quantile: last_close * (1 + predicted_returns[quantile]) for quantile in QUANTILES
        }

        forecasts.append(
            {
                "target_date": target_date,
                "predicted_close": predicted_closes[0.5],
                "confidence_lower": predicted_closes[0.1],
                "confidence_upper": predicted_closes[0.9],
            }
        )

        working_history = append_forecast_row(
            working_history,
            ticker=ticker,
            target_date=pd.Timestamp(target_date),
            close=predicted_closes[0.5],
        )

    return forecasts


def train_ml(
    engine: Engine,
    ticker: str,
    run_date: date | None = None,
) -> dict[str, Any]:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    run_date = run_date or date.today()

    frame = load_training_frame(engine, ticker)
    x_train, x_test, y_train, y_test, feature_names = prepare_xy(frame, TRAIN_TEST_SPLIT)
    models = _train_quantile_models(x_train, y_train)

    prior_close = x_test["close"].to_numpy()
    predicted_returns = models[0.5].predict(x_test)
    actual_returns = y_test.to_numpy()
    metrics = evaluate_return_predictions(actual_returns, predicted_returns, prior_close)

    cleaned = drop_incomplete_rows(frame)
    production_models = _train_quantile_models(
        cleaned[FEATURE_COLUMNS],
        cleaned["next_day_return"],
    )

    seed_history = build_forecast_seed(frame)
    forecast_points = _iterative_forecast(
        seed_history,
        production_models,
        feature_names,
        ticker,
        FORECAST_HORIZON_DAYS,
    )

    model_name = f"{ticker}_ml"
    with mlflow.start_run(run_name=f"{ticker}_ml") as run:
        mlflow.log_params(
            {
                "ticker": ticker,
                "model_type": "ml",
                "horizon_days": FORECAST_HORIZON_DAYS,
                "train_test_split": TRAIN_TEST_SPLIT,
                "quantiles": ",".join(str(q) for q in QUANTILES),
            }
        )
        mlflow.log_metrics(metrics)

        for quantile, model in production_models.items():
            mlflow.xgboost.log_model(
                model,
                artifact_path=f"model_q{int(quantile * 100)}",
            )

        bundle = {
            "feature_names": feature_names,
            "quantiles": list(QUANTILES),
        }
        mlflow.log_dict(bundle, "model_bundle.json")

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as handle:
            pickle.dump(production_models, handle)
            bundle_path = handle.name
        mlflow.log_artifact(bundle_path, artifact_path=".")

        run_id = run.info.run_id

    model_uri = f"runs:/{run_id}/model_q50"
    mlflow.register_model(model_uri, model_name)
    _register_model(model_name)

    forecast_rows = [
        {
            "ticker": ticker,
            "run_date": run_date,
            "target_date": point["target_date"],
            "model_type": "ml",
            "mlflow_run_id": run_id,
            "predicted_close": point["predicted_close"],
            "confidence_lower": point["confidence_lower"],
            "confidence_upper": point["confidence_upper"],
        }
        for point in forecast_points
    ]
    insert_forecasts(engine, forecast_rows)

    logger.info(
        "ML training complete for %s (MAE=%.4f, RMSE=%.4f, dir_acc=%.2f%%)",
        ticker,
        metrics["mae"],
        metrics["rmse"],
        metrics["directional_accuracy"] * 100,
    )
    return {
        "ticker": ticker,
        "model_type": "ml",
        "run_id": run_id,
        "metrics": metrics,
        "forecast_dates": [point["target_date"] for point in forecast_points],
    }
