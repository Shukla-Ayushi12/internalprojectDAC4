# TEAM.md: Who Does What

> This is the single source of truth for task ownership.
> AI agents (Claude Code, Codex) must read this file and only work on the area owned by the person they are helping.
> Folder names refer to the layout in `PROJECT.md`.

## Roles

| # | Member | Workstream | Files/folders they own | Status |
|---|--------|-----------|------------------------|--------|
| 1 | [Ayushi] | Project lead / integration: keeps everyone aligned, merges work | `app.py`, `requirements.txt`, whole repo (review) | Not started |
| 2 | [Ayushi] | Data and model: Kaggle dataset, cleaning, training XGBoost | `data/`, `model/` | Not started |
| 3 | [Akshaya] | Database and services: Supabase tables, data loading, predictor, login | `database/`, `services/` | Not started |
| 4 | [Kaviya] | Student interface | `views/student_dashboard.py` | Not started |
| 5 | [Hannah] | Teacher interface | `views/teacher_dashboard.py` | Not started |
| 6 | [Yuki/Kimi] | Testing, privacy and ethics | `tests/`, `docs/ethics*` | Not started |
| 7 | [Yuan Ling] | Documentation and presentation | `docs/` | Not started |

Shared: `components/` (charts, styles, metric cards) is edited by roles 4 and 5. Tell the other one via `docs/requests.md` before changing something they use.

(With 6 people, merge roles 6 and 7.)

## Task breakdown

### 2. Data and model
- [ ] Download the Kaggle dataset into `data/raw/` (local only, never committed)
- [ ] Write the real column list into `docs/dataset-columns.md`
- [ ] With role 3, decide how the CSV columns map to the database tables
- [ ] Clean data (missing values, formats) into `data/processed/`
- [ ] Make a small anonymised sample in `data/sample/`
- [ ] Train XGBoost model to predict the semester GPA (`model/train.py`)
- [ ] Evaluate (MAE, R²) and write results to `docs/`
- [ ] Save the model file in `model/artifacts/` and write a short "how to use" note

### 3. Database and services
- [ ] Create the Supabase project and share access with the team
- [ ] Write `database/schema.sql` for `students`, `subjects`, `grades` (and the fourth table once decided)
- [ ] Turn on Row Level Security and set who can see what
- [ ] Write `database/seed.py` to load cleaned data into Supabase
- [ ] `services/database.py`: connect to Supabase using secrets
- [ ] `services/data_loader.py`: functions to fetch a student's grades and a class's students (cached)
- [ ] `services/predictor.py`: load the model and return a predicted GPA (use a dummy model until the real one is ready)
- [ ] `services/auth.py`: role selection / login (student vs teacher)

### 4. Student interface
- [ ] Page showing predicted GPA and GPA trend
- [ ] Simple explanation of what influences the prediction
- [ ] Clear disclaimer that it is an estimate

### 5. Teacher interface
- [ ] Class list with predicted GPAs
- [ ] Highlight at-risk students
- [ ] Filter/sort

### 6. Testing, privacy and ethics
- [ ] Test the full flow with sample data
- [ ] Check model fairness across groups
- [ ] Check that students cannot see other students' data
- [ ] Write privacy notes (who can see what)

### 7. Documentation and presentation
- [ ] Meeting notes
- [ ] Final report
- [ ] Slides and demo script

## Dependencies (who waits on whom)
- Interfaces (4, 5) need the function names and outputs from `services/` (role 3). Agree these early.
- Role 3 needs the saved model from role 2 for the predictor (use a dummy model until it's ready).
- Role 3 needs the cleaned data and column mapping from role 2 to seed the database.
- The fourth database table must be decided by the project lead before `schema.sql` is final.