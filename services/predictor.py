"""Score academic snapshots with the saved XGBoost GPA model."""

from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from xgboost.core import XGBoostError


_MODEL_PATH = Path(__file__).resolve().parents[1] / "model/artifacts/gpa_model.json"
_FEATURE_RANGES = {
    "current_cgpa": (0, 4),
    "previous_gpa": (0, 4),
    "attendance": (0, 100),
    "assignment_score": (0, 100),
    "quiz_score": (0, 100),
    "midterm_marks": (0, 100),
    "final_marks": (0, 100),
    "workload_level": (1, 10),
}


@cache
def _load_model() -> tuple[XGBRegressor, list[str], list[str]]:
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(f"GPA model artifact is missing: {_MODEL_PATH}")

    model = XGBRegressor()
    try:
        model.load_model(_MODEL_PATH)
        booster = model.get_booster()
        names = booster.feature_names
        types = booster.feature_types
    except (OSError, TypeError, ValueError, XGBoostError) as error:
        raise RuntimeError(f"Could not load the GPA model: {_MODEL_PATH}") from error

    if (
        not names
        or len(names) != len(set(names))
        or "target_gpa" in names
        or not types
        or len(types) != len(names)
        or set(types) - {"float", "int"}
    ):
        raise RuntimeError("The GPA model must declare unique numeric input features.")
    return model, names, types


def _require_valid(valid: np.ndarray, feature: str, requirement: str) -> None:
    if not valid.all():
        row = np.flatnonzero(~valid)[0]
        raise ValueError(f"Feature {feature!r} at row position {row} {requirement}.")


def _prepare_features(
    features: pd.DataFrame, names: list[str], types: list[str]
) -> pd.DataFrame:
    if features.columns.has_duplicates:
        duplicates = features.columns[features.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate GPA feature columns: {duplicates}.")

    missing = [name for name in names if name not in features.columns]
    unexpected = [column for column in features.columns if column not in names]
    if missing or unexpected:
        raise ValueError(
            f"GPA feature columns do not match: missing {missing}, unexpected {unexpected}."
        )

    ordered = pd.DataFrame(index=features.index)
    for name, feature_type in zip(names, types):
        column = features[name]
        # NumPy timedelta values pass the Real check but carry time units.
        is_number = column.map(
            lambda value: isinstance(value, (Real, Decimal))
            and not isinstance(value, (bool, np.bool_, np.timedelta64))
        )
        _require_valid(is_number.to_numpy(dtype=bool), name, "must contain a numeric value")

        try:
            values = column.to_numpy(dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                f"Feature {name!r} contains a value XGBoost cannot represent."
            ) from error
        # XGBoost uses float32 for its numeric inputs.
        is_representable = np.isfinite(values) & (np.abs(values) <= np.finfo(np.float32).max)
        _require_valid(is_representable, name, "must be finite and within the float32 range")

        if feature_type == "int":
            whole = column.map(lambda value: value == int(value))
            _require_valid(whole.to_numpy(dtype=bool), name, "must be a whole number")

        if name in _FEATURE_RANGES:
            low, high = _FEATURE_RANGES[name]
            in_range = column.between(low, high).to_numpy(dtype=bool)
            _require_valid(in_range, name, f"must be between {low} and {high}")
        elif name in {"study_hours_week", "backlog_subjects"}:
            _require_valid(column.ge(0).to_numpy(dtype=bool), name, "must be non-negative")

        ordered[name] = values
    return ordered


def predict_gpas(features: pd.DataFrame) -> pd.Series:
    """Return raw GPA estimates in input row order, retaining the input index.

    Each row must provide exactly the model's named features. An invalid row
    rejects the batch before inference.
    """
    if not isinstance(features, pd.DataFrame):
        raise TypeError("Batch GPA prediction expects a pandas DataFrame.")

    model, names, types = _load_model()
    ordered = _prepare_features(features, names, types)
    if ordered.empty:
        return pd.Series(index=features.index, dtype="float32", name="predicted_gpa")

    try:
        predictions = model.predict(ordered)
    except XGBoostError as error:
        raise RuntimeError("XGBoost could not generate GPA predictions.") from error

    if predictions.shape != (len(ordered),) or not np.isfinite(predictions).all():
        raise RuntimeError("The GPA model must return one finite prediction per input row.")
    return pd.Series(predictions, index=features.index, name="predicted_gpa")


def predict_gpa(features: Mapping[str, Real | Decimal]) -> float:
    """Return the model's raw GPA estimate for one named feature snapshot."""
    if not isinstance(features, Mapping):
        raise TypeError("Single GPA prediction expects a mapping of feature names to values.")
    batch = pd.DataFrame([dict(features)])
    return float(predict_gpas(batch).iloc[0])
