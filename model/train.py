"""Trains the XGBoost model that predicts next-semester GPA.

Run from the project folder with:  python model/train.py

Reads : data/processed/cleaned_dataset.csv   (made by data/clean_data.py)
Writes: model/artifacts/gpa_model.json        (the trained model)
        model/artifacts/feature_importance.csv (which inputs matter most)
"""
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "processed" / "cleaned_dataset.csv"
ARTIFACTS = ROOT / "model" / "artifacts"

SEED = 42  # fixed so results are the same every time
TARGET = "target_gpa"  # what we predict
# Inputs = every other column. Nothing here uses the GPA being predicted.
FEATURES = [
    "current_cgpa", "previous_gpa", "attendance", "assignment_score",
    "quiz_score", "midterm_marks", "final_marks", "study_hours_week",
    "backlog_subjects", "workload_level",
]


def load_splits():
    """Splits the data: 80% for learning, 20% kept aside for testing.

    evaluate.py calls this too, so both files use the exact same test rows.
    """
    df = pd.read_csv(DATA_FILE)
    X, y = df[FEATURES], df[TARGET]
    return train_test_split(X, y, test_size=0.2, random_state=SEED)


def main():
    if not DATA_FILE.exists():
        raise SystemExit(f"Cannot find {DATA_FILE}. Run data/clean_data.py first.")

    X_train, X_test, y_train, y_test = load_splits()

    # Keep a small slice of the learning data to know when to stop training.
    # The test rows stay untouched, so the final score is honest.
    X_fit, X_val, y_fit, y_val = train_test_split(
        X_train, y_train, test_size=0.1, random_state=SEED
    )

    model = XGBRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        early_stopping_rounds=30,
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_fit, y_fit, eval_set=[(X_val, y_val)], verbose=False)
    print(f"Training stopped at {model.best_iteration + 1} trees")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    model.save_model(ARTIFACTS / "gpa_model.json")

    importance = pd.DataFrame(
        {"feature": FEATURES, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)
    importance.to_csv(ARTIFACTS / "feature_importance.csv", index=False)

    print(f"Saved model to {ARTIFACTS / 'gpa_model.json'}")
    print("\nMost important inputs:")
    print(importance.to_string(index=False))


if __name__ == "__main__":
    main()
