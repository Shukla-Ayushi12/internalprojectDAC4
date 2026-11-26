"""Generate and validate a fictional GPA demo, with no database connection.

Run from the repository root with `.venv/bin/python -B -m database.seed`.
Add `--output /tmp/gpa-demo.sql` to export one owner-run PostgreSQL transaction.
The transaction expects the three demo teacher emails in TEACHERS to have existing
Auth accounts with app_role=module_teacher. It does not create logins or forecasts.
Run it against the seven-table schema. Rerunning the same input preserves existing
student Auth links and revisions. Changed academic values require --allow-corrections
and owner review. Affected historical forecasts remain stored and become stale.

Demonstration grading policy (minimum percentage, letter, grade points):
A 80/4.0, B+ 75/3.5, B 70/3.0, C+ 65/2.5, C 60/2.0, D+ 55/1.5,
D 50/1.0, F 0/0.0. The lower boundary is inclusive and 100 is a valid A.
No retakes, withdrawals, incomplete grades or exceptional credits are simulated.
The matched Kaggle attendance is the semester target, rounded to two decimals.
Module offsets are credit-centred, scaled to stay in 0–100%, and rounded to four
decimals. The unrounded weighted mean is within 0.00005 percentage points of
that target. The stored two-decimal mean equals the rounded Kaggle attendance.
Each completed F stays in the backlog for v1. Planned modules count only toward
expected next-semester credits. GPA/CGPA are rounded to 12 decimal places after
dividing total quality points by credits. Attendance is rounded to two places.

The reproducible default uses the checked-in Kaggle-derived sample. The source
reference records the donor filename, SHA-256 and one-based parsed data row
(excluding the header and blank lines). Attendance and all six assessment and
behavioural features come from that row. GPA, CGPA and backlog are synthetic.
"""

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from random import Random

import pandas as pd

from services.predictor import predict_gpas


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data/sample/sample_dataset.csv"
SEED = 20261125
COHORT_SIZE = 24
TEACHERS = tuple(f"gpa-demo-teacher-{i}@example.com" for i in range(1, 4))
GRADE_SCALE = (
    (80, "A", Decimal("4.0")),
    (75, "B+", Decimal("3.5")),
    (70, "B", Decimal("3.0")),
    (65, "C+", Decimal("2.5")),
    (60, "C", Decimal("2.0")),
    (55, "D+", Decimal("1.5")),
    (50, "D", Decimal("1.0")),
    (0, "F", Decimal("0.0")),
)
CALENDAR = (
    ("Y1S1", "Year 1 Semester 1", date(2025, 1, 13), date(2025, 5, 2)),
    ("Y1S2", "Year 1 Semester 2", date(2025, 8, 11), date(2025, 12, 5)),
    ("Y2S1", "Year 2 Semester 1", date(2026, 1, 12), date(2026, 5, 1)),
    ("Y2S2", "Year 2 Semester 2", date(2026, 8, 10), date(2026, 12, 4)),
)
CURRICULUM = (
    (("MTH101", "Applied Mathematics", 4), ("PRG101", "Programming Basics", 3),
     ("COM101", "Academic Communication", 2)),
    (("STA102", "Applied Statistics", 4), ("DAT102", "Data Literacy", 4),
     ("WEB102", "Web Development", 3)),
    (("DBS201", "Database Systems", 4), ("VIS201", "Data Visualisation", 3),
     ("SYS201", "Systems Foundations", 3)),
    (("RES202", "Research Methods", 3), ("ANA202", "Applied Analytics", 4),
     ("PRJ202", "Team Project", 5)),
)
KAGGLE_FEATURES = (
    "assignment_score", "quiz_score", "midterm_marks", "final_marks",
    "study_hours_week", "workload_level",
)
KAGGLE_PROVENANCE = ("attendance", *KAGGLE_FEATURES)
MATCH_FEATURES = ("current_cgpa", "previous_gpa", "attendance", "backlog_subjects")
FEATURES = (
    "current_cgpa", "previous_gpa", "attendance", "assignment_score", "quiz_score",
    "midterm_marks", "final_marks", "study_hours_week", "backlog_subjects", "workload_level",
)
TWO_PLACES = Decimal("0.01")
MODULE_ATTENDANCE_PRECISION = Decimal("0.0001")
GPA_PRECISION = Decimal("0.000000000001")


def grade_points(score: Decimal) -> Decimal:
    """Convert a finite percentage using the demo grading scale."""
    if not score.is_finite() or not 0 <= score <= 100:
        raise ValueError(f"Invalid module percentage: {score}")
    return next(points for minimum, _, points in GRADE_SCALE if score >= minimum)


def _percentage(value: float) -> Decimal:
    return Decimal(str(min(100, max(0, value)))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _module_attendance(target: Decimal, credits: list[int], deviations: list[float]) -> list[Decimal]:
    offsets = [Decimal(str(value)) for value in deviations]
    mean = sum(offset * credit for offset, credit in zip(offsets, credits, strict=True)) / sum(credits)
    offsets = [offset - mean for offset in offsets]
    scale = Decimal(1)
    if max(offsets) > 0:
        scale = min(scale, (100 - target) / max(offsets))
    if min(offsets) < 0:
        scale = min(scale, target / -min(offsets))
    return [
        (target + scale * offset).quantize(MODULE_ATTENDANCE_PRECISION, rounding=ROUND_HALF_UP)
        for offset in offsets
    ]


def _load_donors(source: Path) -> tuple[pd.DataFrame, str]:
    # Read one version of the file for both the hash and the parsed values.
    contents = source.read_bytes()
    donors = pd.read_csv(BytesIO(contents), usecols=list(FEATURES))[list(FEATURES)]
    if donors.empty:
        raise ValueError("The donor CSV has no data rows.")
    bounds = dict.fromkeys(FEATURES, (0, 100))
    bounds.update(current_cgpa=(0, 4), previous_gpa=(0, 4), study_hours_week=(0, 168),
                  backlog_subjects=(0, 20), workload_level=(1, 10))
    for feature, (minimum, maximum) in bounds.items():
        donors[feature] = column = pd.to_numeric(donors[feature], errors="raise")
        if not column.between(minimum, maximum).all() or column.isna().any():
            raise ValueError(f"Invalid donor values in {feature}.")
        if feature in {"backlog_subjects", "workload_level"} and not column.mod(1).eq(0).all():
            raise ValueError(f"The donor feature {feature} must contain whole numbers.")
    return donors, f"{source.name}:sha256:{sha256(contents).hexdigest()}"


def generate_demo(source: Path = SAMPLE, seed: int = SEED) -> dict:
    """Build a cohort and its labelled, traceable academic snapshots in memory."""
    donors, version = _load_donors(source)
    donor_inputs = donors[list(MATCH_FEATURES)].to_numpy(dtype=float)
    scales = donors[list(MATCH_FEATURES)].std(ddof=0).clip(lower=0.1).to_numpy()
    rng = Random(seed)
    terms = []
    modules = []
    for term_number, (suffix, name, start, end) in enumerate(CALENDAR, 1):
        semester_id = -1100 - term_number
        completed = term_number < len(CALENDAR)
        midnight = datetime.combine(end, time.min, timezone.utc)
        terms.append({
            "semester_id": semester_id, "semester_code": f"DEMO-{suffix}",
            "semester_name": f"Demo {name}", "term_order": term_number,
            "starts_on": start.isoformat(), "ends_on": end.isoformat(),
            "next_semester_id": semester_id - 1 if completed else None,
            "finalized_at": (midnight + timedelta(days=1)).isoformat() if completed else None,
            "forecast_cutoff_at": (midnight + timedelta(days=7)).isoformat() if completed else None,
        })
        for offset, (code, title, credits) in enumerate(CURRICULUM[term_number - 1]):
            module_index = len(modules) + 1
            modules.append({
                "module_id": -1200 - module_index, "module_code": f"DEMO-{code}",
                "module_name": f"Demo {title}", "semester_id": semester_id,
                "offering_id": -1300 - module_index,
                "teacher_email": TEACHERS[(offset + term_number - 1) % len(TEACHERS)],
                "gpa_credits": credits,
            })

    module_difficulty = {m["module_id"]: rng.gauss(0, 2.5) for m in modules}
    students, results, summaries = [], [], []
    for index in range(COHORT_SIZE):
        student_id = -1001 - index
        students.append({"student_id": student_id, "display_name": f"Demo Student {index + 1:02d}"})
        # Stable student ability and attendance tendencies drive correlated results across terms.
        ability = (61, 62, 64)[index] if index < 3 else rng.gauss(74, 7)
        attendance_base = 76 + (ability - 74) * 0.55 + rng.gauss(0, 4)
        cumulative_points = Decimal(0)
        cumulative_credits = backlog = 0
        term_shift = 0.0
        personal_drift = rng.gauss(0.4, 0.9)
        for term in terms:
            semester_id = term["semester_id"]
            term_modules = [m for m in modules if m["semester_id"] == semester_id]
            term_shift = 0.5 * term_shift + rng.gauss(0, 3)
            # One student builds a strong record before a temporary setback in Year 2.
            setback = index == 3 and term["term_order"] == 3
            year_one_boost = 7 if index == 3 and term["term_order"] < 3 else 0
            term_points = Decimal(0)
            term_credits = 0
            term_results = []
            deviations = []
            for module_number, module in enumerate(term_modules):
                score = None
                if term["finalized_at"]:
                    score = _percentage(ability + personal_drift * (term["term_order"] - 1)
                                        + term_shift + module_difficulty[module["module_id"]]
                                        + rng.gauss(0, 4.5) + year_one_boost - (23 if setback else 0))
                    if index < 3 and term["term_order"] == 1 and module_number == 0:
                        score = (Decimal("54.99"), Decimal("55.00"), Decimal("55.01"))[index]
                    deviations.append(rng.gauss(0, 4))
                    credits = module["gpa_credits"]
                    points = grade_points(score)
                    term_points += points * credits
                    term_credits += credits
                    backlog += int(points == 0)
                term_results.append({
                    "offering_id": module["offering_id"], "student_id": student_id,
                    "attendance_percent": None, "actual_score_percent": score,
                })
            results.extend(term_results)
            if not term["finalized_at"]:
                continue
            cumulative_points += term_points
            cumulative_credits += term_credits
            gpa = (term_points / term_credits).quantize(GPA_PRECISION, rounding=ROUND_HALF_UP)
            cgpa = (cumulative_points / cumulative_credits).quantize(GPA_PRECISION, rounding=ROUND_HALF_UP)
            credits = [module["gpa_credits"] for module in term_modules]
            # The simulated tendency helps choose a donor. The donor sets actual demo attendance.
            attendance_hint = attendance_base + 0.4 * term_shift - (14 if setback else 0)
            attendance_hint += sum(value * credit for value, credit in zip(deviations, credits)) / term_credits
            anchor = [float(cgpa), float(gpa), float(_percentage(attendance_hint)), backlog]
            distance = ((donor_inputs - anchor) / scales) ** 2
            # GPA and attendance anchor the match, with less weight on backlog.
            donor_index = int((distance @ [1.0, 1.0, 1.0, 0.25]).argmin())
            donor = donors.iloc[donor_index]
            attendance = Decimal(str(donor["attendance"])).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            for result, module_attendance in zip(term_results, _module_attendance(attendance, credits, deviations),
                                                 strict=True):
                result["attendance_percent"] = module_attendance
            summary = {
                "student_id": student_id, "semester_id": semester_id,
                "semester_gpa": gpa, "cumulative_gpa": cgpa,
                "semester_gpa_credits": term_credits, "cumulative_gpa_credits": cumulative_credits,
                "expected_next_semester_credits": sum(
                    m["gpa_credits"] for m in modules if m["semester_id"] == term["next_semester_id"]
                ),
                "attendance": attendance, "backlog_subjects": backlog,
                "kaggle_source_ref": f"{version}:row:{donor_index + 1}",
                "kaggle_feature_names": KAGGLE_PROVENANCE,
            }
            summary.update({name: float(donor[name]) for name in KAGGLE_FEATURES})
            summary["workload_level"] = int(donor["workload_level"])
            summaries.append(summary)
    return {
        "terms": terms, "students": students, "modules": modules, "results": results,
        "summaries": summaries,
        "grade_scale": [{"minimum": minimum, "points": points} for minimum, _, points in GRADE_SCALE],
    }


def model_inputs(demo: dict) -> pd.DataFrame:
    """Return the ten model inputs at each completed-semester cutoff, in summary order."""
    return pd.DataFrame(demo["summaries"]).rename(columns={
        "semester_gpa": "previous_gpa", "cumulative_gpa": "current_cgpa",
    })[list(FEATURES)]


def preview_warnings(demo: dict) -> Counter:
    """Check model compatibility and preview student warnings without publishing forecasts."""
    counts = Counter()
    predictions = predict_gpas(model_inputs(demo))
    for record, prediction in zip(demo["summaries"], predictions, strict=True):
        raw = float(prediction)
        bounded = Decimal(format(max(0.0, min(4.0, raw)), ".15g"))
        past_credits = record["cumulative_gpa_credits"]
        future_credits = record["expected_next_semester_credits"]
        projected = (record["cumulative_gpa"] * past_credits + bounded * future_credits) / (
            past_credits + future_credits
        )
        counts[raw <= 2.2, projected <= Decimal("2.2")] += 1
    return counts


def render_seed_sql(demo: dict, *, allow_corrections: bool = False) -> str:
    """Make a reviewable, self-contained transaction to run as the database owner."""
    payload = json.dumps(demo, default=str, allow_nan=False, separators=(",", ":"))
    literal = "'" + payload.replace("'", "''") + "'"
    staging = (
        "create temporary table demo_input on commit drop as\n"
        f"select {literal}::jsonb as payload, {str(allow_corrections).lower()} as allow_corrections;"
    )
    template = (Path(__file__).with_name("finalize_demo.sql")).read_text(encoding="utf-8")
    return template.replace("-- DEMO_INPUT", staging, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SAMPLE, help="Kaggle-derived donor CSV")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, help="export to a new local SQL file")
    parser.add_argument("--allow-corrections", action="store_true",
                        help="let the owner replace changed academic values in this demo cohort")
    args = parser.parse_args()
    try:
        demo = generate_demo(args.source, args.seed)
        warnings = preview_warnings(demo)
        if args.output:
            sql = render_seed_sql(demo, allow_corrections=args.allow_corrections)
            with args.output.open("x", encoding="utf-8") as output:
                output.write(sql)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Demo seed failed: {error}\n")
    scores = [r["actual_score_percent"] for r in demo["results"] if r["actual_score_percent"] is not None]
    print(f"Demo seed {args.seed}: {len(demo['students'])} students, {len(TEACHERS)} teachers, "
          f"{len(demo['terms'])} terms and {len(demo['modules'])} module offerings")
    print(f"{len(scores)} completed results, {len(demo['results']) - len(scores)} planned enrolments, "
          f"{len(demo['summaries'])} completed-semester summaries")
    print(f"Module scores below / at / above 55%: {sum(s < 55 for s in scores)} / "
          f"{sum(s == 55 for s in scores)} / {sum(s > 55 for s in scores)}")
    print(f"Student warning preview: GPA only {warnings[True, False]}, CGPA only {warnings[False, True]}, "
          f"both {warnings[True, True]}, neither {warnings[False, False]}")
    if args.output:
        print(f"Owner-run SQL transaction written to {args.output}")


if __name__ == "__main__":
    main()
