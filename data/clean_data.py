"""Cleans the raw GPA dataset and saves tidy copies.

Run from the project folder with:  python data/clean_data.py

Reads : data/raw/perfect_academic_dataset_1m.csv   (never committed to GitHub)
Writes: data/processed/cleaned_dataset.csv          (full cleaned data, kept local)
        data/sample/sample_dataset.csv              (1,000 rows, safe to commit)
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "perfect_academic_dataset_1m.csv"
CLEAN_FILE = ROOT / "data" / "processed" / "cleaned_dataset.csv"
SAMPLE_FILE = ROOT / "data" / "sample" / "sample_dataset.csv"

SEED = 42  # fixed so the sample is the same every time

# The allowed range for each column (from docs/dataset-columns.md).
# A row outside these ranges is impossible, so it is removed.
VALID_RANGES = {
    "current_cgpa": (0, 4),
    "previous_gpa": (0, 4),
    "attendance": (0, 100),
    "assignment_score": (0, 100),
    "quiz_score": (0, 100),
    "midterm_marks": (0, 100),
    "final_marks": (0, 100),
    "study_hours_week": (0, 168),  # a week only has 168 hours
    "backlog_subjects": (0, 20),
    "workload_level": (1, 10),
    "target_gpa": (0, 4),
}


def main():
    if not RAW_FILE.exists():
        raise SystemExit(f"Cannot find {RAW_FILE}. Put the CSV in data/raw/ first.")

    df = pd.read_csv(RAW_FILE)
    print(f"Rows at the start: {len(df):,}")

    # 1. Check that every expected column is there.
    missing_cols = set(VALID_RANGES) - set(df.columns)
    if missing_cols:
        raise SystemExit(f"Missing columns: {missing_cols}")

    # 2. Remove rows with empty values.
    before = len(df)
    df = df.dropna()
    print(f"Removed {before - len(df):,} rows with empty values")

    # 3. Remove exact duplicate rows.
    before = len(df)
    df = df.drop_duplicates()
    print(f"Removed {before - len(df):,} duplicate rows")

    # 4. Remove rows with impossible values (outside the allowed ranges).
    before = len(df)
    for col, (low, high) in VALID_RANGES.items():
        df = df[df[col].between(low, high)]
    print(f"Removed {before - len(df):,} rows with impossible values")

    # 5. Make sure whole-number columns are stored as whole numbers.
    df["backlog_subjects"] = df["backlog_subjects"].astype(int)
    df["workload_level"] = df["workload_level"].astype(int)

    # 6. Save the cleaned data and a small sample.
    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_FILE, index=False)
    df.sample(n=1000, random_state=SEED).to_csv(SAMPLE_FILE, index=False)

    print(f"Rows at the end: {len(df):,}")
    print(f"Saved: {CLEAN_FILE}")
    print(f"Saved: {SAMPLE_FILE}")


if __name__ == "__main__":
    main()
    