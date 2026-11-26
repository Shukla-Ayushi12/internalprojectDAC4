"""Teacher page: a teacher's class list with predicted GPAs and at-risk students.

This page only arranges things on screen. Its data should come from
services/ (owned by the Database and services role). Until those functions
exist, a TEMPORARY sample-data section below fills the page so it can be
built and tested. See docs/requests.md for what the page needs.

Preview on its own with:  streamlit run views/teacher_dashboard.py
"""
import sys
from pathlib import Path

# Lets this file find the shared components/ folder when previewed on its
# own. Harmless when app.py loads the page.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from components.charts import gpa_distribution

DEFAULT_AT_RISK_BELOW = 2.0  # GPA under 2.0 is a common academic-warning line

# Columns this page expects in the table it is given.
REQUIRED_COLUMNS = [
    "student", "class_name", "predicted_gpa",
    "current_cgpa", "attendance", "backlog_subjects",
]


# ---------------------------------------------------------------------------
# TEMPORARY: sample data stand-in.
# Delete this section once services/ provides the teacher's class list with
# predictions. The dataset has no student names, IDs, teachers or classes,
# so these labels and classes are made up for testing only.
# ---------------------------------------------------------------------------
@st.cache_data
def _load_sample_class_list() -> pd.DataFrame:
    from xgboost import XGBRegressor  # only needed for the stand-in

    sample = pd.read_csv(ROOT / "data" / "sample" / "sample_dataset.csv").head(120)
    model = XGBRegressor()
    model.load_model(ROOT / "model" / "artifacts" / "gpa_model.json")

    # Use the model's own input list, so the target column is never fed in.
    features = list(model.get_booster().feature_names)
    sample["predicted_gpa"] = model.predict(sample[features]).clip(0, 4)

    sample["student"] = [f"Sample student {i + 1:03d}" for i in range(len(sample))]
    sample["class_name"] = [f"Sample class {'ABCD'[i // 30]}" for i in range(len(sample))]
    return sample[REQUIRED_COLUMNS]
# --------------------------- end of TEMPORARY ------------------------------


def render_teacher_dashboard(class_list: pd.DataFrame) -> None:
    """Draws the teacher page from a table with the REQUIRED_COLUMNS."""
    st.title("My classes: predicted GPAs")
    st.info(
        "All GPAs on this page are **estimates** from a computer model, "
        "not guarantees. Use them as a starting point for a conversation, "
        "never as a final judgement about a student."
    )

    # --- Sidebar filters ---
    st.sidebar.header("Filters")
    classes = sorted(class_list["class_name"].unique())
    chosen_class = st.sidebar.selectbox("Class", ["All my classes"] + classes)
    at_risk_below = st.sidebar.slider(
        "At-risk if predicted GPA is below",
        min_value=1.0, max_value=3.5, value=DEFAULT_AT_RISK_BELOW, step=0.1,
    )
    only_at_risk = st.sidebar.checkbox("Show only at-risk students")

    table = class_list.copy()
    if chosen_class != "All my classes":
        table = table[table["class_name"] == chosen_class]
    table["at_risk"] = table["predicted_gpa"] < at_risk_below
    table["change"] = table["predicted_gpa"] - table["current_cgpa"]

    if table.empty:
        st.warning("No students to show for this class.")
        return

    # --- Key numbers ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Students", len(table))
    col2.metric("Average predicted GPA", f"{table['predicted_gpa'].mean():.2f}")
    col3.metric(
        "At-risk students",
        int(table["at_risk"].sum()),
        help=f"Predicted GPA below {at_risk_below:.1f}",
    )

    # --- Spread of predictions ---
    st.subheader("How predicted GPAs are spread")
    st.altair_chart(
        gpa_distribution(table["predicted_gpa"], at_risk_below),
        width="stretch",
    )

    # --- Student list (click a column header to sort) ---
    st.subheader("Students")
    shown = table[table["at_risk"]] if only_at_risk else table
    shown = shown.sort_values("predicted_gpa")  # lowest first: who needs help
    st.caption("Lowest predicted GPA first. Click a column header to sort differently.")
    st.dataframe(
        shown[[
            "student", "class_name", "at_risk", "predicted_gpa", "change",
            "current_cgpa", "attendance", "backlog_subjects",
        ]],
        hide_index=True,
        width="stretch",
        column_config={
            "student": "Student",
            "class_name": "Class",
            "at_risk": st.column_config.CheckboxColumn("At risk"),
            "predicted_gpa": st.column_config.ProgressColumn(
                "Predicted GPA (estimate)", min_value=0, max_value=4, format="%.2f"
            ),
            "change": st.column_config.NumberColumn(
                "Change vs current CGPA", format="%+.2f"
            ),
            "current_cgpa": st.column_config.NumberColumn("Current CGPA", format="%.2f"),
            "attendance": st.column_config.NumberColumn("Attendance", format="%.0f%%"),
            "backlog_subjects": "Failed/pending subjects",
        },
    )

    with st.expander("About this page"):
        st.markdown(
            f"""
- **Predicted GPA** is an estimate of next semester's GPA from an XGBoost
  model. On test data it was off by about 0.03 GPA points on average, but
  the training data is synthetic, so real accuracy may be lower.
- **At risk** means the predicted GPA is below {at_risk_below:.1f}. You can
  move this line in the sidebar.
- **Change vs current CGPA** shows whether the student is predicted to go
  up (+) or down (−) compared with their GPA so far.
- You only see students in your own classes.
"""
        )


# Preview this page on its own until app.py loads it.
if __name__ == "__main__":
    st.set_page_config(page_title="Teacher dashboard", layout="wide")
    st.caption("Preview with made-up sample data (not real students).")
    render_teacher_dashboard(_load_sample_class_list())
