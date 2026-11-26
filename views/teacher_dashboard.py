"""Teacher page: results, attendance and intervention flags for a teacher's modules.

This page only arranges things on screen. All data comes from services/
(see services/README.md). Teachers see module results for their assigned
offerings only. GPA forecasts are student-only, so they are not shown here.

app.py should call:  render_teacher_dashboard(data, session)
  data    = services.data_loader.DashboardData(...)
  session = the signed-in teacher's session (already refreshed)

Preview on its own with:  streamlit run views/teacher_dashboard.py
  - With .streamlit/secrets.toml present: sign in as a demo teacher.
  - Without it: made-up sample modules and students (no database needed).
"""
import sys
from pathlib import Path

# Lets this file find services/ and components/ when previewed on its own.
# Harmless when app.py loads the page.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from components.charts import score_distribution
from services.database import SupabaseError

FLAG_AT_OR_BELOW = 55  # Project rule: a module score <= 55% needs intervention

STATUS_FLAGGED = "Needs attention"
STATUS_PENDING = "Result pending"
STATUS_OK = "On track"


def _offering_label(offering: dict) -> str:
    module = offering["module"]
    return f"{module['module_code']} {module['module_name']} (section {offering['section_code']})"


def _status(row: dict) -> str:
    # Follow the backend contract: flag only when is_module_at_risk is True.
    if row.get("is_module_at_risk") is True:
        return STATUS_FLAGGED
    if row.get("actual_score_percent") is None:
        return STATUS_PENDING
    return STATUS_OK


def _roster_table(roster: list[dict]) -> pd.DataFrame:
    """Turns the backend roster into a display table, flagged students first."""
    table = pd.DataFrame([
        {
            "student": (row.get("student") or {}).get("display_name", "Unknown"),
            "status": _status(row),
            "score": row.get("actual_score_percent"),
            "grade_points": row.get("grade_points"),
            "attendance": row.get("attendance_percent"),
            "completed_at": pd.to_datetime(row.get("completed_at"), utc=True).date()
            if row.get("completed_at") else None,
        }
        for row in roster
    ])
    for column in ["score", "grade_points", "attendance"]:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    order = {STATUS_FLAGGED: 0, STATUS_PENDING: 1, STATUS_OK: 2}
    return table.sort_values(
        by=["status", "score"], key=lambda col: col.map(order) if col.name == "status" else col
    ).reset_index(drop=True)


def render_teacher_dashboard(data, session) -> None:
    """Draws the teacher page for a signed-in module teacher."""
    st.title("My modules")
    st.caption(
        f"Students scoring {FLAG_AT_OR_BELOW}% or below in a module are flagged "
        "for follow-up. GPA forecasts are shown only to the students themselves."
    )

    try:
        offerings = data.teacher_modules(session)
    except PermissionError:
        st.error("This page is for teachers. Please sign in with a teacher account.")
        return
    except SupabaseError:
        st.error("Could not load your modules. Check your connection and sign in again.")
        return

    if not offerings:
        st.info("You have no modules assigned yet. Contact the project admin if this is wrong.")
        return

    # --- Sidebar filters (newest semester first, as the backend sorts them) ---
    st.sidebar.header("Filters")
    semesters = list(dict.fromkeys(o["semester"]["semester_name"] for o in offerings))
    chosen_semester = st.sidebar.selectbox("Semester", semesters)
    in_semester = [o for o in offerings if o["semester"]["semester_name"] == chosen_semester]
    chosen = st.sidebar.selectbox("Module", in_semester, format_func=_offering_label)
    only_flagged = st.sidebar.checkbox("Show only students needing attention")

    try:
        roster = data.teacher_roster(session, chosen["offering_id"])
    except SupabaseError:
        st.error("Could not load this module's students. Please try again.")
        return

    st.subheader(_offering_label(chosen))
    if not roster:
        st.info("No students are enrolled in this module yet.")
        return

    table = _roster_table(roster)

    # --- Key numbers ---
    recorded = table["score"].notna()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Students", len(table))
    col2.metric(
        "Need attention", int((table["status"] == STATUS_FLAGGED).sum()),
        help=f"Module score {FLAG_AT_OR_BELOW}% or below",
    )
    col3.metric("Results pending", int((~recorded).sum()))
    col4.metric(
        "Average score",
        f"{table.loc[recorded, 'score'].mean():.0f}%" if recorded.any() else "–",
    )

    # --- Spread of scores ---
    if recorded.any():
        st.markdown("**How scores are spread**")
        st.altair_chart(score_distribution(table["score"], FLAG_AT_OR_BELOW), width="stretch")

    # --- Student list (click a column header to sort) ---
    st.markdown("**Students**")
    shown = table[table["status"] == STATUS_FLAGGED] if only_flagged else table
    st.caption("Students needing attention first. Click a column header to sort differently.")
    st.dataframe(
        shown,
        hide_index=True,
        width="stretch",
        column_config={
            "student": "Student",
            "status": "Status",
            "score": st.column_config.NumberColumn("Score", format="%.0f%%"),
            "grade_points": st.column_config.NumberColumn("Grade points", format="%.2f"),
            "attendance": st.column_config.ProgressColumn(
                "Attendance", min_value=0, max_value=100, format="%.0f%%"
            ),
            "completed_at": st.column_config.DateColumn("Result recorded"),
        },
    )

    with st.expander("About this page"):
        st.markdown(
            f"""
- You only see students enrolled in modules assigned to you.
- **Needs attention** means the student's module score is {FLAG_AT_OR_BELOW}% or below.
- **Result pending** means no score has been recorded yet. These students are
  still listed so nobody is missed.
- GPA forecasts are **estimates** and are shown only to each student on their
  own page, not to teachers.
"""
        )


# ---------------------------------------------------------------------------
# PREVIEW ONLY: lets this page run on its own until app.py loads it.
# ---------------------------------------------------------------------------
class _SampleTeacherData:
    """Made-up modules and students with the same shape as DashboardData.

    Used only when no Supabase settings are present. Not real students.
    """

    def __init__(self):
        import random

        rng = random.Random(42)  # same sample every time
        semesters = [
            {"semester_id": 2, "semester_name": "Sample Semester 2", "term_order": 2},
            {"semester_id": 1, "semester_name": "Sample Semester 1", "term_order": 1},
        ]
        modules = [
            ("SMP101", "Sample Statistics", semesters[0], "A"),
            ("SMP102", "Sample Economics", semesters[0], "B"),
            ("SMP101", "Sample Statistics", semesters[1], "A"),
        ]
        self._offerings, self._rosters = [], {}
        for offering_id, (code, name, semester, section) in enumerate(modules, start=1):
            self._offerings.append({
                "offering_id": offering_id, "section_code": section, "semester": semester,
                "module": {"module_code": code, "module_name": name},
            })
            roster = []
            for n in range(1, 21):
                pending = offering_id == 1 and n > 17  # newest module: a few not marked yet
                score = None if pending else round(min(100, max(20, rng.gauss(68, 14))), 1)
                roster.append({
                    "student": {"display_name": f"Sample student {offering_id}{n:02d}"},
                    "actual_score_percent": score,
                    "grade_points": None if pending else round(min(4, max(0, (score - 40) / 15)), 2),
                    "attendance_percent": round(min(100, max(40, rng.gauss(85, 10))), 1),
                    "completed_at": None if pending else "2026-11-20T00:00:00+00:00",
                    "is_module_at_risk": None if pending else score <= FLAG_AT_OR_BELOW,
                })
            self._rosters[offering_id] = roster

    def teacher_modules(self, session):
        return self._offerings

    def teacher_roster(self, session, offering_id):
        return self._rosters.get(offering_id, [])


def _preview_with_sign_in(settings) -> None:
    """Minimal teacher sign-in for local testing against the development database."""
    from services.auth import AuthService
    from services.data_loader import DashboardData

    auth = AuthService(settings["url"], settings["publishable_key"])
    data = DashboardData(settings["url"], settings["publishable_key"])

    session = st.session_state.get("gpa_session")
    if session is None:
        with st.form("teacher_sign_in"):
            st.subheader("Teacher sign-in (preview)")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in"):
                try:
                    st.session_state["gpa_session"] = auth.sign_in(email, password)
                    st.rerun()
                except (SupabaseError, PermissionError):
                    st.error("Sign-in failed. Check the email and password.")
        return

    try:
        session = auth.refresh_if_needed(session)
        st.session_state["gpa_session"] = session
    except SupabaseError:
        st.session_state.pop("gpa_session", None)
        st.warning("Your session expired. Please sign in again.")
        st.rerun()

    if st.sidebar.button("Sign out"):
        try:
            auth.sign_out(session)
        finally:
            st.session_state.pop("gpa_session", None)
            st.rerun()

    render_teacher_dashboard(data, session)


if __name__ == "__main__":
    st.set_page_config(page_title="Teacher dashboard", layout="wide")
    try:
        supabase_settings = st.secrets["supabase"]
    except Exception:  # no secrets file: run on sample data
        supabase_settings = None

    if supabase_settings:
        _preview_with_sign_in(supabase_settings)
    else:
        from services.auth import Session

        st.caption("Preview with made-up sample data (not real students).")
        sample_session = Session("sample-teacher", "module_teacher", 0, "", "")
        render_teacher_dashboard(_SampleTeacherData(), sample_session)
