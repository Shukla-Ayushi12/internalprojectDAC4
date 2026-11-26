"""Reusable chart functions for the Streamlit pages.

Shared by the student and teacher pages. Before changing a function the
other page uses, leave a note in docs/requests.md (see TEAM.md).
"""
import altair as alt
import pandas as pd


def score_distribution(scores: pd.Series, flag_at_or_below: float) -> alt.Chart:
    """Histogram of module scores (0-100%), with a red line at the flag cut-off.

    Teachers use it to see at a glance how a module's results are spread and
    how many students fall at or below the intervention line.
    """
    data = pd.DataFrame({"Score (%)": scores.dropna()})

    bars = (
        alt.Chart(data)
        .mark_bar(color="#4C78A8")
        .encode(
            x=alt.X(
                "Score (%):Q",
                bin=alt.Bin(extent=[0, 100], step=5),
                title="Module score (%)",
            ),
            y=alt.Y("count():Q", title="Number of students"),
            tooltip=[alt.Tooltip("count():Q", title="Students")],
        )
    )

    cutoff = (
        alt.Chart(pd.DataFrame({"cutoff": [flag_at_or_below]}))
        .mark_rule(color="#D62728", strokeDash=[6, 4], size=2)
        .encode(x="cutoff:Q", tooltip=[alt.Tooltip("cutoff:Q", title="Flag line (%)")])
    )

    return (bars + cutoff).properties(height=260)
