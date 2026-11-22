"""Measures how accurate the trained model is, on rows it has never seen.

Run from the project folder with:  python model/evaluate.py
(Run model/train.py first.)

Writes: docs/model-results.md
"""
from pathlib import Path
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

from train import ARTIFACTS, ROOT, load_splits

RESULTS_FILE = ROOT / "docs" / "model-results.md"


def main():
    model_file = ARTIFACTS / "gpa_model.json"
    if not model_file.exists():
        raise SystemExit("No trained model found. Run model/train.py first.")

    _, X_test, _, y_test = load_splits()
    model = XGBRegressor()
    model.load_model(model_file)
    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    # Two simple guesses to compare against. The model should beat both.
    mae_average = mean_absolute_error(y_test, [y_test.mean()] * len(y_test))
    mae_same_as_now = mean_absolute_error(y_test, X_test["current_cgpa"])

    print(f"Test rows: {len(y_test):,}")
    print(f"MAE: {mae:.3f} GPA points (average error)")
    print(f"R2 : {r2:.3f} (1.0 = perfect)")
    print(f"Guess the average GPA every time -> MAE {mae_average:.3f}")
    print(f"Guess 'same as current CGPA'     -> MAE {mae_same_as_now:.3f}")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(f"""# Model Results

**Model:** XGBoost regressor (random seed 42)
**Target:** `target_gpa`
**Inputs:** the other 10 columns (see `dataset-columns.md`)
**Split:** 80% training, 20% testing ({len(y_test):,} test rows the model never saw)

## Accuracy on the test rows

| Measure | Value | What it means |
|---------|-------|---------------|
| MAE | {mae:.3f} | On average, the prediction is off by this many GPA points |
| R² | {r2:.3f} | Share of the differences between students that the model explains (1.0 = perfect) |

## Comparison with simple guesses

| Method | MAE |
|--------|-----|
| Guess the average GPA for everyone | {mae_average:.3f} |
| Guess "next GPA = current CGPA" | {mae_same_as_now:.3f} |
| **XGBoost model** | **{mae:.3f}** |

## Notes

- The data is synthetic, so real-world accuracy may differ.
- Predictions are estimates, not guarantees.
""", encoding="utf-8")
    print(f"\nSaved results to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
