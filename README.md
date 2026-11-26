# Student GPA Prediction System

The system gives students access to their own academic history and next-semester GPA estimates. Teachers can view results for their assigned module offerings and identify scores at or below 55%. The development backend uses a fictional cohort, Supabase Auth and PostgreSQL, and a saved XGBoost model.

**Current state.** The database, demo data, forecast publisher, sign-in, and dashboard data services are implemented and verified in the development project. The Streamlit app shell, dashboard pages, and browser-level integration are still pending in this checkout.

## Local setup

From the repository root, reuse the existing `.venv` if present. For a fresh macOS or Linux checkout, use Python 3.13. The environment was verified with Python 3.13.12.

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

On Windows, use `py -3.13 -m venv .venv` and substitute `.venv\Scripts\python.exe` for `.venv/bin/python`. In VS Code, select the project `.venv` with **Python: Select Interpreter**.

`requirements.txt` is unpinned. To reproduce the main package versions verified during backend development, use this install command in place of the general install above. Pip still resolves the other transitive dependencies.

```sh
.venv/bin/python -m pip install -r requirements.txt \
  'streamlit==1.67.0' 'pandas==3.1.1' 'xgboost==3.4.1' \
  'scikit-learn==1.9.1' 'supabase==2.34.1' 'altair==6.3.0' \
  'plotly==7.1.0' 'httpx==0.28.1' 'numpy==2.5.5'
```

The HTTP transport imports `httpx`, and the predictor imports `numpy`. The current requirements install both transitively.

## Verify the backend locally

```sh
.venv/bin/python -B -m unittest -v services.test_backend
.venv/bin/python -B -m database.seed
```

The first command runs 12 service tests with local fixtures and mocks. The second generates the synthetic cohort in memory and scores its snapshots with the saved model. Both use the repository files and can run with no Supabase credentials, raw Kaggle download, or model retraining. Use the [dashboard integration guide](services/README.md) for the verified hosted checks and the remaining UI acceptance tests.

## Find the right guide

| I want to… | Start here |
| --- | --- |
| Understand the architecture, business rules, or completion status | [Project specification](internalprojectDAC4/PROJECT.md) |
| Set up a fresh development database, prepare demo accounts, or run the seed | [Database runbook](database/README.md) |
| Integrate a dashboard or run the forecast publisher | [Backend and dashboard integration guide](services/README.md) |
| Understand dataset fields, model features, or the reported accuracy | [Dataset and feature mapping](docs/dataset-columns.md) and [Model results](docs/model-results.md) |
| Find the owner of a file or share changes | [Team roles](internalprojectDAC4/TEAM.md) and [Workflow](internalprojectDAC4/WORKFLOW.md) |

The dashboard uses the Supabase project URL, a publishable key, and a signed-in user session. Use ignored local or deployment secrets for the dashboard configuration. The publisher uses a secret key in a trusted operator environment. Follow the team’s secure handoff for demo passwords.
