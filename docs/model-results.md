# Model Results

**Model:** XGBoost regressor (random seed 42)
**Target:** `target_gpa`
**Inputs:** the other 10 columns (see `dataset-columns.md`)
**Split:** 80% development data, 20% held-out testing (200,000 test rows). Training splits the development portion again for fit and early-stopping validation.

## Accuracy on the test rows

| Measure | Value | What it means |
|---------|-------|---------------|
| MAE | 0.029 | On average, the prediction is off by this many GPA points |
| R² | 0.995 | Share of the variance in held-out `target_gpa` explained by the model (1.0 is a perfect fit). |

## Comparison with simple guesses

| Method | MAE |
|--------|-----|
| Predict the test set's mean GPA for every row | 0.409 |
| Guess "next GPA = current CGPA" | 0.167 |
| **XGBoost model** | **0.029** |

## Notes

- These are the recorded results on held-out rows from the synthetic dataset. The mean baseline uses the held-out target mean as a reference. Treat the metrics as demo evidence and see the [dataset limitations](dataset-columns.md#training-and-demo-use) for real-world evaluation needs.
- [evaluate.py](../model/evaluate.py) regenerates this report when run with the full cleaned dataset and a saved model. Routine backend checks use the saved artifact and checked-in sample.
