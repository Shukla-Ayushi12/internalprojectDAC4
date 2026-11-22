# Dataset Columns

**Dataset:** Semester GPA Prediction Dataset (Kaggle, asadirfanmzg)
**File:** `perfect_academic_dataset_1m.csv`
**Size:** 1,000,000 rows, 11 columns
**Data quality:** no missing values, no duplicate rows
**Note:** The data is synthetic (not real students).

## Columns

| Column | Type | Meaning | Range |
|--------|------|---------|-------|
| `current_cgpa` | decimal | Student's cumulative GPA so far | 0.68 – 4.0 |
| `previous_gpa` | decimal | GPA from the previous semester | 0.22 – 4.0 |
| `attendance` | decimal | Attendance percentage | 33.1 – 100 |
| `assignment_score` | decimal | Assignment score | 29.5 – 100 |
| `quiz_score` | decimal | Quiz score | 22.6 – 100 |
| `midterm_marks` | decimal | Midterm exam marks | 14.7 – 100 |
| `final_marks` | decimal | Final exam marks | 21.0 – 100 |
| `study_hours_week` | decimal | Study hours per week | 0 – 57.9 |
| `backlog_subjects` | whole number | Number of failed or pending subjects | 0 – 10 |
| `workload_level` | whole number | Workload rating | 1 – 10 |
| `target_gpa` | decimal | **The GPA the model predicts** | 0.44 – 4.0 |

## Target and inputs

- **Target (what we predict):** `target_gpa`
- **Inputs (what the model uses):** the other 10 columns

## What the dataset does NOT contain

- No student ID
- No subject or course
- No semester number
- No teacher or class

Each row is one student's snapshot plus the GPA to predict. This affects the database design, so the project lead must decide how to handle it (see `docs/requests.md`).

## Assumptions to confirm

- The score columns (assignments, quiz, midterm, final) belong to the *current* semester, and `target_gpa` is the *next* semester's GPA. If this is wrong, some inputs could leak the answer and must be removed.
- Postgres-friendly names: all column names are already lowercase with underscores, so no renaming is needed for the database.

## Strongest links to the target (correlation)

`current_cgpa` 0.94, `previous_gpa` 0.90, `final_marks` 0.81, `assignment_score` 0.80, `midterm_marks` 0.79, `quiz_score` 0.79, `attendance` 0.72, `backlog_subjects` -0.61, `study_hours_week` 0.39, `workload_level` -0.08
