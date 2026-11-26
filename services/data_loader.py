"""Dashboard data assembled through the signed-in user's Supabase session."""

from datetime import datetime, timezone

from services.auth import Session
from services.database import SupabaseAPI, require_publishable_key


STUDENT = "student_id,display_name"
SEMESTER = "semester_id,semester_code,semester_name,term_order,starts_on,ends_on"
OFFERING = (
    "offering_id,section_code,module:modules(module_id,module_code,module_name),"
    f"semester:semesters({SEMESTER})"
)
RESULT = (
    "offering_id,student_id,attendance_percent,completed_at,actual_score_percent,"
    "grade_points,is_module_at_risk"
)
HISTORY = f"semester_gpa,cumulative_gpa,finalized_at,record_origin,semester:semesters({SEMESTER})"
FORECAST = (
    "source_semester_id,target_semester_id,published_at,displayed_predicted_gpa,projected_cgpa,"
    "is_predicted_gpa_at_risk,is_projected_cgpa_at_risk"
)


def _module_results(api: SupabaseAPI, **filters) -> list[dict]:
    return api.select("module_enrolments", f"{RESULT},offering:module_offerings({OFFERING})",
                      order="offering_id.asc,student_id.asc", **filters)


def _latest_completed_semester(history: list[dict], results: list[dict]) -> int | None:
    # A corrected term may vanish from the reconciled history until finalisation.
    # Completed module results in an ended term still identify the newer semester.
    today = datetime.now(timezone.utc).date().isoformat()
    completed = [record["semester"] for record in history]
    for result in results:
        term = result["offering"]["semester"]
        if result["completed_at"] and term["ends_on"] <= today:
            completed.append(term)
    return max(completed, key=lambda term: term["term_order"])["semester_id"] if completed else None


class DashboardData:
    def __init__(self, url: str, publishable_key: str):
        require_publishable_key(publishable_key)
        self.url = url
        self._key = publishable_key

    def _api(self, session: Session, role: str) -> SupabaseAPI:
        if session.role != role or not session.access_token:
            raise PermissionError("This action requires the matching signed-in role.")
        return SupabaseAPI(self.url, self._key, session.access_token)

    def student_profile(self, session: Session) -> dict | None:
        """Return the signed-in student's profile, or None for an unlinked account."""
        with self._api(session, "student") as api:
            students = api.select("students", STUDENT, order="student_id.asc")
            if not students:
                return None
            if len(students) != 1:
                raise RuntimeError("Expected a single student linked to this session.")
            student = students[0]
            scope = {"student_id": f"eq.{student['student_id']}"}
            results = _module_results(api, **scope)
            history = api.select("semester_records", HISTORY, order="semester_id.asc", **scope)
            history.sort(key=lambda row: row["semester"]["term_order"], reverse=True)
            latest = _latest_completed_semester(history, results)
            forecast = None
            if latest is not None:
                rows = api.select("forecasts", FORECAST, order="source_semester_id.asc", **scope,
                                  source_semester_id=f"eq.{latest}")
                if rows and rows[0]["displayed_predicted_gpa"] is not None:
                    forecast = rows[0]
                    targets = api.select("semesters", SEMESTER, order="semester_id.asc",
                                         semester_id=f"eq.{forecast['target_semester_id']}")
                    forecast["target_semester"] = targets[0] if targets else None
            return {"student": student, "module_results": results, "semester_history": history,
                    "latest_forecast": forecast}

    def teacher_modules(self, session: Session) -> list[dict]:
        with self._api(session, "module_teacher") as api:
            rows = api.select("module_offerings", OFFERING, order="offering_id.asc")
        return sorted(rows, key=lambda row: (-row["semester"]["term_order"], row["module"]["module_code"]))

    def teacher_roster(self, session: Session, offering_id: int) -> list[dict]:
        """Return all accessible enrolments for this offering, including unflagged and pending."""
        with self._api(session, "module_teacher") as api:
            return api.select("module_enrolments", f"{RESULT},student:students({STUDENT})",
                              order="student_id.asc", offering_id=f"eq.{offering_id}")

    def teacher_student_profile(self, session: Session, student_id: int) -> dict | None:
        """Return only the selected student's results for this teacher's offerings."""
        with self._api(session, "module_teacher") as api:
            scope = {"student_id": f"eq.{student_id}"}
            students = api.select("students", STUDENT, order="student_id.asc", **scope)
            if not students:
                return None
            results = _module_results(api, **scope)
            return {"student": students[0], "module_results": results} if results else None
