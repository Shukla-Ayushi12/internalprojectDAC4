# Dataset and feature mapping

The model workstream profiled the synthetic [Semester GPA Prediction Dataset](https://www.kaggle.com/datasets/asadirfanmzg/semester-gpa-prediction-dataset). Its source file, `perfect_academic_dataset_1m.csv`, was documented with 1,000,000 rows, 11 columns, and no missing or duplicate rows. The repository includes a [1,000-row sample](../data/sample/sample_dataset.csv) with the same column names. The ranges and correlations below come from the original source profile.

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

## Training and demo use

The rows are synthetic academic snapshots. Student identities, module results, semester identifiers, and teaching assignments come from the demo generator. The dataset provides no timeline or stable student identifiers for validating predictions across real terms.

For training, `target_gpa` is the label and the other ten columns are features. The model workflow interprets the recorded scores as inputs available at prediction time and `target_gpa` as the next-semester outcome. This interpretation is a modelling assumption. Longitudinal data with explicit terms and feature timestamps would be needed to validate it for real use. Predictions describe the synthetic demo setting.

The [cleaning script](../data/clean_data.py) reads the download from `data/raw/`, checks columns and valid ranges, removes missing rows and duplicates, and writes to `data/processed/` and `data/sample/`. Raw and processed data directories are ignored. The saved artifact and checked-in sample support ordinary backend development. Rerunning [training](../model/train.py) writes the model and importance artifacts. Rerunning [evaluation](../model/evaluate.py) regenerates the Markdown metrics report.

## Demo feature mapping

The publisher reads the following features from the student's latest eligible `semester_records` row.

| Model feature | Database column | Demo value source |
| --- | --- | --- |
| `current_cgpa` | `cumulative_gpa` | Calculated from all completed module results and credits to date. |
| `previous_gpa` | `semester_gpa` | Calculated from module results and credits in the completed source term. |
| `attendance` | `attendance` | Matched sample row. Module attendance is reconciled to this term value. |
| `assignment_score`, `quiz_score`, `midterm_marks`, `final_marks` | Same names | Copied together from the matched sample row. |
| `study_hours_week`, `workload_level` | Same names | Copied from the same matched sample row. |
| `backlog_subjects` | `backlog_subjects` | Cumulative count of completed modules graded F under the demo policy. |

The generator compares synthetic GPA, CGPA, an attendance hint, and backlog to the sample rows. It scales the differences by column spread and gives backlog a quarter of the weight of each other matching feature. `kaggle_source_ref` identifies the donor CSV by filename, SHA-256, and one-based parsed data row. `kaggle_feature_names` identifies the seven inputs taken from that row. The demo imports academic facts and model inputs. Predictions come from the saved model at publication time.

See the [generator](../database/seed.py), [academic policy](../database/README.md#demo-academic-policy), and [publisher mapping](../services/forecast_publisher.py).

## Strongest links to the target (correlation)

`current_cgpa` 0.94, `previous_gpa` 0.90, `final_marks` 0.81, `assignment_score` 0.80, `midterm_marks` 0.79, `quiz_score` 0.79, `attendance` 0.72, `backlog_subjects` -0.61, `study_hours_week` 0.39, `workload_level` -0.08
