# Model Results

**Model:** XGBoost regressor (random seed 42)
**Target:** `target_gpa`
**Inputs:** the other 10 columns (see `dataset-columns.md`)
**Split:** 80% training, 20% testing (200,000 test rows the model never saw)

## Accuracy on the test rows

| Measure | Value | What it means |
|---------|-------|---------------|
| MAE | 0.029 | On average, the prediction is off by this many GPA points |
| R² | 0.995 | Share of the differences between students that the model explains (1.0 = perfect) |

## Comparison with simple guesses

| Method | MAE |
|--------|-----|
| Guess the average GPA for everyone | 0.409 |
| Guess "next GPA = current CGPA" | 0.167 |
| **XGBoost model** | **0.029** |

## Notes

- The data is synthetic, so real-world accuracy may differ.
- Predictions are estimates, not guarantees.
