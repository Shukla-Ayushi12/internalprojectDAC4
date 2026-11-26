# Backend and dashboard integration

This guide is the contract for the Streamlit integration. The service methods have passed live Supabase checks. The application pages and their browser-level tests are the next integration step.

## Configure the Streamlit server

Use the development project URL and its **publishable** key in `.streamlit/secrets.toml` locally or deployment secrets. The following example uses names the Streamlit shell can read and pass to the service constructors.

```toml
[supabase]
url = "https://YOUR_PROJECT_REF.supabase.co"
publishable_key = "YOUR_SUPABASE_PUBLISHABLE_KEY"
```

The service constructors take the values explicitly. Supabase identifies the caller from the user's access token and applies Row Level Security (RLS) on each data request. The publisher's elevated key belongs only to the operator workflow. [Supabase API keys and user sessions](https://supabase.com/docs/guides/getting-started/api-keys)

## Sign in and manage a session

```python
import streamlit as st

from services.auth import AuthService
from services.data_loader import DashboardData

settings = st.secrets["supabase"]
auth = AuthService(settings["url"], settings["publishable_key"])
data = DashboardData(settings["url"], settings["publishable_key"])
st.session_state["gpa_session"] = auth.sign_in(email, password)
```

Use the form's `email` and `password` only on submission. Before fetching data, refresh the stored session with `session = auth.refresh_if_needed(st.session_state["gpa_session"])` and save the returned session back under `gpa_session`. Route according to `session.role`, either `student` or `module_teacher`, which comes from administrator-managed Supabase metadata. On sign-out, call `auth.sign_out(session)` and clear the stored session in a `finally` block. Prompt the user to sign in again if refresh fails. Keep tokens and user-scoped responses in per-user server-side state and out of rendered output, logs, and shared caches.

## Read dashboard data

| Dashboard call | Result |
| --- | --- |
| `data.student_profile(session)` | `student`, `module_results`, `semester_history` (newest first), and `latest_forecast`. Returns `None` for an unlinked account. |
| `data.teacher_modules(session)` | Assigned offerings, including historical ones. Each has `offering_id`, `section_code`, `module`, and `semester`. |
| `data.teacher_roster(session, offering_id)` | Accessible enrolments and their `student` identities. Includes unflagged students and pending results. An empty list also covers an inaccessible offering. |
| `data.teacher_student_profile(session, student_id)` | A `student` and their `module_results` for this teacher's assigned offerings. Returns `None` for an inaccessible student. |

Module results expose `offering_id`, `student_id`, `completed_at`, `actual_score_percent`, `grade_points`, `attendance_percent`, and `is_module_at_risk`. Profile results also include `offering` with module and term metadata. Pending results have `None` for unrecorded fields. For teachers, flag results only when `is_module_at_risk is True` (actual score ≤ 55%).

Student history entries include the actual `semester_gpa` and `cumulative_gpa`, `finalized_at`, `record_origin`, and nested `semester` metadata. Forecasts include `source_semester_id`, `target_semester_id`, `published_at`, `displayed_predicted_gpa`, `projected_cgpa`, `target_semester`, `is_predicted_gpa_at_risk`, and `is_projected_cgpa_at_risk`. Display the two warnings separately using the returned booleans. Show **Prediction unavailable** when `latest_forecast` is `None`. A forecast can have a GPA estimate and a `None` projected CGPA when projected credits are unavailable. Label estimates separately from actual results.

Catch `SupabaseError` from `services.database` to display a login or connection message. A `PermissionError` means the user lacks the role for that operation.

## Forecast publishing

Run manually after approved [academic finalisation](../database/README.md#set-up-the-fictional-cohort). Set the non-secret `SUPABASE_URL` and `SUPABASE_PROJECT_REF` to the development project's values. The command prompts privately for the project secret key if `SUPABASE_SECRET_KEY` is absent from the publisher's environment. Keep that key in the operator environment only.

```sh
.venv/bin/python -B -m services.forecast_publisher --url "$SUPABASE_URL"
.venv/bin/python -B -m services.forecast_publisher --url "$SUPABASE_URL" --publish --project-ref "$SUPABASE_PROJECT_REF"
```

The first command is a dry run. Initial publication is limited to the latest eligible records. An identical rerun preserves existing forecast rows and publication timestamps. For an approved correction, add `--correction-reason "New reason for the changed revision or model"` and review the dry run first. This applies to eligible changed forecasts in that run. The database computes projected CGPA and both forecast flags. Review any `needs_correction_approval`, `changed_during_run`, or `unavailable` counts before publishing again.

## Verification and UI handoff

- Run the local service tests with `.venv/bin/python -B -m unittest -v services.test_backend`. These cover candidate selection, missing inputs, dry runs, stale revisions, request construction, session handling, and scoped profile responses with mocks.
- Local PostgreSQL checks exercised the schema, exact 55% and 2.2 boundaries, and invalidation and correction rules. The repository currently contains the Python service suite. The PostgreSQL and hosted verification harnesses were run separately during development.
- Live Supabase tests verified 24 linked student accounts, four representative student sessions, three teacher sessions, session refresh and logout, module isolation, and forecast privacy. The first batch of 24 forecasts was scored in Python and applied through SQL Editor. The Python publisher's live rerun matched all 24 existing forecasts with zero writes. First-time API inserts and correction requests have local coverage.
- Kaviya and Hannah should verify the integrated UI with signed-in demo users. Cover pending results, unavailable forecasts, both independent warning states, unflagged teacher roster entries, session expiry, and cross-user isolation. Browser rendering and the deployed Streamlit application still need acceptance testing.
