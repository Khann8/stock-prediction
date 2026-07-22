"""Evaluation metrics for baseline and ML models."""

import numpy as np


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def directional_accuracy(
    actual_returns: np.ndarray,
    predicted_returns: np.ndarray,
) -> float:
    if len(actual_returns) == 0:
        return 0.0

    actual_sign = np.sign(actual_returns)
    predicted_sign = np.sign(predicted_returns)
    matches = actual_sign == predicted_sign
    zero_mask = (actual_sign == 0) & (predicted_sign == 0)
    return float(np.mean(matches | zero_mask))


def evaluate_close_predictions(
    actual_close: np.ndarray,
    predicted_close: np.ndarray,
    prior_close: np.ndarray,
) -> dict[str, float]:
    actual_returns = (actual_close - prior_close) / prior_close
    predicted_returns = (predicted_close - prior_close) / prior_close
    return {
        "mae": mae(actual_close, predicted_close),
        "rmse": rmse(actual_close, predicted_close),
        "directional_accuracy": directional_accuracy(actual_returns, predicted_returns),
    }


def evaluate_return_predictions(
    actual_returns: np.ndarray,
    predicted_returns: np.ndarray,
    prior_close: np.ndarray,
) -> dict[str, float]:
    predicted_close = prior_close * (1 + predicted_returns)
    actual_close = prior_close * (1 + actual_returns)
    return evaluate_close_predictions(actual_close, predicted_close, prior_close)
