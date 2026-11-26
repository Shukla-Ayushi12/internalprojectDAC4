"""Review or publish next-semester forecasts with a trusted development credential."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from getpass import getpass
from hashlib import sha256
import os
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from services.database import SupabaseAPI, SupabaseError
from services.predictor import predict_gpa, predict_gpas


MODEL_FILE = Path(__file__).resolve().parents[1] / "model/artifacts/gpa_model.json"
MODEL_FIELDS = {
    "current_cgpa": "cumulative_gpa", "previous_gpa": "semester_gpa", "attendance": "attendance",
    "assignment_score": "assignment_score", "quiz_score": "quiz_score", "midterm_marks": "midterm_marks",
    "final_marks": "final_marks", "study_hours_week": "study_hours_week",
    "backlog_subjects": "backlog_subjects", "workload_level": "workload_level",
}
RECORD_COLUMNS = ",".join(("student_id", "semester_id", "finalized_at", "record_revision",
                           "reconciled_revision", *MODEL_FIELDS.values()))
FORECAST_COLUMNS = "student_id,source_semester_id,published_at,source_record_revision,model_artifact,raw_predicted_gpa"


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def plan_forecasts(
    records: list[dict], calendar: list[dict], forecasts: list[dict], model: str,
    *, as_of: datetime, correction_reason: str | None = None,
) -> tuple[list[tuple[dict, dict | None]], Counter]:
    """Select and score eligible latest snapshots. Return writes and aggregate outcomes."""
    terms = {row["semester_id"]: row for row in calendar}
    previous = {(row["student_id"], row["source_semester_id"]): row for row in forecasts}
    latest = {}
    for row in records:
        if _timestamp(row["finalized_at"]) <= as_of:
            student = row["student_id"]
            existing = latest.get(student)
            if existing is None or terms[row["semester_id"]]["term_order"] > terms[existing["semester_id"]]["term_order"]:
                latest[student] = row

    counts = Counter(latest_records=len(latest))
    candidates = []
    for student, row in sorted(latest.items()):
        source = terms[row["semester_id"]]
        target = terms.get(source["next_semester_id"])
        cutoff = source["forecast_cutoff_at"]
        features = {name: row[field] for name, field in MODEL_FIELDS.items()}
        if (row["record_revision"] != row["reconciled_revision"] or not target
                or target["term_order"] <= source["term_order"] or not cutoff
                or not _timestamp(row["finalized_at"]) <= _timestamp(cutoff) <= as_of
                or any(value is None for value in features.values())):
            counts["unavailable"] += 1
            continue
        existing = previous.get((student, source["semester_id"]))
        if (existing and existing["source_record_revision"] == row["record_revision"]
                and existing["model_artifact"] == model and existing["raw_predicted_gpa"] is not None):
            counts["unchanged"] += 1
            continue
        if existing and not correction_reason:
            counts["needs_correction_approval"] += 1
            continue
        payload = {"student_id": student, "source_semester_id": source["semester_id"],
                   "target_semester_id": target["semester_id"], "source_record_revision": row["record_revision"],
                   "model_artifact": model}
        if existing:
            payload.update(published_at="now", republication_reason=correction_reason)
        candidates.append((payload, existing, features))

    if not candidates:
        return [], counts
    try:
        raw_scores = list(predict_gpas(pd.DataFrame([features for _, _, features in candidates])))
    except ValueError:
        # A malformed input should not prevent scoring otherwise eligible students.
        raw_scores = []
        for _, _, features in candidates:
            try:
                raw_scores.append(predict_gpa(features))
            except ValueError:
                raw_scores.append(None)
    planned = []
    for (payload, existing, _), raw in zip(candidates, raw_scores, strict=True):
        if raw is None:
            counts["unavailable"] += 1
            continue
        payload["raw_predicted_gpa"] = float(raw)
        counts["ready_to_correct" if existing else "ready_to_insert"] += 1
        planned.append((payload, existing))
    return planned, counts


def _publish(api: SupabaseAPI, planned: list[tuple[dict, dict | None]], counts: Counter) -> None:
    for payload, existing in planned:
        try:
            if existing is None:
                published = api.request(
                    "POST", "/rest/v1/forecasts", operation="insert forecast", json=payload,
                    params={"on_conflict": "student_id,source_semester_id", "select": "student_id"},
                    headers={"Prefer": "resolution=ignore-duplicates,missing=default,return=representation"},
                )
            else:
                patch = {k: payload[k] for k in ("source_record_revision", "model_artifact", "raw_predicted_gpa",
                                                 "published_at", "republication_reason")}
                published = api.request(
                    "PATCH", "/rest/v1/forecasts", operation="republish forecast", json=patch,
                    params={"student_id": f"eq.{payload['student_id']}",
                            "source_semester_id": f"eq.{payload['source_semester_id']}",
                            "published_at": f"eq.{existing['published_at']}",
                            "source_record_revision": f"eq.{existing['source_record_revision']}",
                            "select": "student_id"}, headers={"Prefer": "return=representation"},
                )
        except SupabaseError as error:
            if error.code not in {"23514", "P0002"}:
                raise
            current = api.select("semester_records", "record_revision,reconciled_revision", order="semester_id.asc",
                                 student_id=f"eq.{payload['student_id']}",
                                 semester_id=f"eq.{payload['source_semester_id']}")
            revision = payload["source_record_revision"]
            if not current or current[0]["record_revision"] != revision or current[0]["reconciled_revision"] != revision:
                counts["changed_during_run"] += 1
                continue
            raise
        counts[("corrected" if existing else "inserted") if published else "already_handled"] += 1


def run(url: str, key: str, *, publish: bool = False, reason: str | None = None) -> Counter:
    if not key.startswith("sb_secret_"):
        raise ValueError("The trusted publisher requires a Supabase secret key.")
    if reason is not None and not reason.strip():
        raise ValueError("A correction reason must contain text.")
    model = f"{MODEL_FILE.name}:sha256:{sha256(MODEL_FILE.read_bytes()).hexdigest()}"
    with SupabaseAPI(url, key) as api:
        calendar = api.select("semesters", "semester_id,term_order,next_semester_id,forecast_cutoff_at",
                              order="term_order.asc")
        records = api.select("semester_records", RECORD_COLUMNS, order="student_id.asc,semester_id.asc")
        forecasts = api.select("forecasts", FORECAST_COLUMNS, order="student_id.asc,source_semester_id.asc")
        planned, counts = plan_forecasts(records, calendar, forecasts, model, as_of=datetime.now(timezone.utc),
                                         correction_reason=reason)
        if publish:
            _publish(api, planned, counts)
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL"))
    parser.add_argument("--publish", action="store_true", help="write the latest forecasts")
    parser.add_argument("--project-ref", help="confirm the matching Supabase project before writing")
    parser.add_argument("--correction-reason", help="explicit reason to republish a changed forecast")
    args = parser.parse_args()
    if not args.url:
        parser.error("Provide --url or SUPABASE_URL.")
    if args.publish and (not args.project_ref or urlsplit(args.url).hostname != f"{args.project_ref}.supabase.co"):
        parser.error("Publishing requires --project-ref matching the project URL.")
    try:
        key = os.getenv("SUPABASE_SECRET_KEY") or getpass("Supabase publisher secret key: ")
        counts = run(args.url, key, publish=args.publish, reason=args.correction_reason)
    except (RuntimeError, ValueError, OSError) as error:
        parser.exit(1, f"Forecast run failed: {error}\n")
    print("Publish" if args.publish else "Dry run", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
