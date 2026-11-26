"""Reusable chart functions for the Streamlit pages.

Shared by the student and teacher pages. Before changing a function the
other page uses, leave a note in docs/requests.md (see TEAM.md).
"""
import altair as alt
import pandas as pd


def gpa_distribution(predicted_gpas: pd.Series, at_risk_below: float) -> alt.Chart:
    """Histogram of predicted GPAs, with a red line at the at-risk cut-off.

    Teachers use it to see at a glance how the class is spread out and how
    many students fall below the line.
    """
    data = pd.DataFrame({"Predicted GPA": predicted_gpas})

    bars = (
        alt.Chart(data)
        .mark_bar(color="#4C78A8")
        .encode(
            x=alt.X(
                "Predicted GPA:Q",
                bin=alt.Bin(extent=[0, 4], step=0.25),
                title="Predicted GPA (estimate)",
            ),
            y=alt.Y("count():Q", title="Number of students"),
            tooltip=[alt.Tooltip("count():Q", title="Students")],
        )
    )

    cutoff = (
        alt.Chart(pd.DataFrame({"cutoff": [at_risk_below]}))
        .mark_rule(color="#D62728", strokeDash=[6, 4], size=2)
        .encode(x="cutoff:Q", tooltip=[alt.Tooltip("cutoff:Q", title="At-risk line")])
    )

    return (bars + cutoff).properties(height=280)
