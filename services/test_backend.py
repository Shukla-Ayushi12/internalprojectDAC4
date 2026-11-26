"""Run with .venv/bin/python -B -m unittest services.test_backend."""

from collections import Counter
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

import httpx
import pandas as pd

from services.auth import AuthService, Session
from services.data_loader import DashboardData
from services.database import SupabaseAPI, SupabaseError
from services.forecast_publisher import MODEL_FIELDS, _publish, plan_forecasts, run


URL = "https://demo.supabase.co"
KEY = "sb_publishable_test_fixture"
AS_OF = datetime(2026, 11, 26, tzinfo=timezone.utc)
MODEL = "test-model"


def term(number):
    return {"semester_id": -number, "term_order": number, "next_semester_id": -number - 1,
            "forecast_cutoff_at": "2026-06-01T00:00:00Z", "ends_on": "2026-05-25"}


def record(student, number, **changes):
    values = dict(zip(MODEL_FIELDS.values(), (2.4, 2.2, 71, 63, 58, 60, 65, 20, 0, 4), strict=True))
    values.update(student_id=student, semester_id=-number, finalized_at="2026-05-30T00:00:00Z",
                  record_revision=1, reconciled_revision=1)
    return {**values, **changes}


def session(role):
    return Session("test-id", role, 0, "test-user-token", "test-refresh-token")


class PublisherTests(unittest.TestCase):
    @patch("services.forecast_publisher.predict_gpas", return_value=pd.Series([2.123]))
    def test_latest_reconciled_snapshot_and_no_fallback(self, score):
        rows = [record(-1, 1), record(-1, 2, semester_gpa=1.75), record(-2, 1),
                record(-2, 2, attendance=None), record(-3, 2, reconciled_revision=None),
                record(-4, 2, finalized_at="2027-01-01T00:00:00Z")]
        planned, counts = plan_forecasts(rows, [term(1), term(2), term(3)], [], MODEL, as_of=AS_OF)
        self.assertEqual(counts, Counter(latest_records=3, unavailable=2, ready_to_insert=1))
        self.assertEqual(planned[0][0]["target_semester_id"], -3)
        self.assertEqual(planned[0][0]["raw_predicted_gpa"], 2.123)
        pd.testing.assert_frame_equal(score.call_args.args[0], pd.DataFrame([{
            "current_cgpa": 2.4, "previous_gpa": 1.75, "attendance": 71, "assignment_score": 63,
            "quiz_score": 58, "midterm_marks": 60, "final_marks": 65, "study_hours_week": 20,
            "backlog_subjects": 0, "workload_level": 4,
        }]))

    @patch("services.forecast_publisher.predict_gpas", return_value=pd.Series([2.1]))
    def test_noop_and_explicit_correction(self, score):
        calendars = [term(1), term(2)]
        existing = {"student_id": -1, "source_semester_id": -1, "source_record_revision": 1,
                    "published_at": "2026-07-10T00:00:00Z", "model_artifact": MODEL, "raw_predicted_gpa": 2.1}
        plan, counts = plan_forecasts([record(-1, 1)], calendars, [existing], MODEL, as_of=AS_OF)
        self.assertEqual((plan, counts["unchanged"]), ([], 1))
        score.assert_not_called()
        fixed = record(-1, 1, record_revision=2, reconciled_revision=2)
        plan, counts = plan_forecasts([fixed], calendars, [existing], MODEL, as_of=AS_OF)
        self.assertEqual((plan, counts["needs_correction_approval"]), ([], 1))
        plan, counts = plan_forecasts([fixed], calendars, [existing], MODEL, as_of=AS_OF,
                                      correction_reason="Reviewed correction to revision 2")
        self.assertEqual(counts["ready_to_correct"], 1)
        transport = Mock()
        transport.request.return_value = [{"student_id": -1}]
        _publish(transport, plan, counts)
        args, kwargs = transport.request.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertEqual(kwargs["params"]["published_at"], "eq.2026-07-10T00:00:00Z")
        self.assertEqual(kwargs["json"]["published_at"], "now")
        self.assertEqual(counts["corrected"], 1)

    def test_publish_rechecks_a_stale_revision_and_ignores_duplicate_insert(self):
        row = {"student_id": 1, "source_semester_id": 2, "source_record_revision": 1}
        transport = Mock()
        transport.request.side_effect = [SupabaseError("insert forecast", 400, "23514"), []]
        transport.select.return_value = [{"record_revision": 2, "reconciled_revision": 2}]
        counts = Counter()
        _publish(transport, [(row, None), (row, None)], counts)
        self.assertEqual(counts, Counter(changed_during_run=1, already_handled=1))
        self.assertIn("resolution=ignore-duplicates", transport.request.call_args.kwargs["headers"]["Prefer"])

    @patch("services.forecast_publisher.predict_gpa", side_effect=[ValueError("invalid"), 2.8])
    @patch("services.forecast_publisher.predict_gpas", side_effect=ValueError("invalid input"))
    def test_malformed_input_does_not_block_other_students(self, _batch, _single):
        plan, counts = plan_forecasts([record(-2, 1), record(-1, 1)], [term(1), term(2)], [], MODEL,
                                      as_of=AS_OF)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(plan[0][0]["student_id"], -1)

    @patch("services.forecast_publisher.SupabaseAPI")
    @patch("services.forecast_publisher.predict_gpas", return_value=pd.Series([2.1]))
    def test_default_dry_run_scores_without_writing(self, _score, connect):
        api = connect.return_value.__enter__.return_value
        api.select.side_effect = [[term(1), term(2)], [record(-1, 1)], []]
        self.assertEqual(run(URL, "sb_secret_test_fixture")["ready_to_insert"], 1)
        api.request.assert_not_called()

    def test_unapproved_cutoff_and_missing_target_skip_latest_record(self):
        cutoff = term(2)
        cutoff["forecast_cutoff_at"] = "2027-02-01T00:00:00Z"
        plan, counts = plan_forecasts([record(-1, 1), record(-1, 2), record(-2, 3)],
                                      [term(1), cutoff, term(3)], [], MODEL, as_of=AS_OF)
        self.assertEqual((plan, counts["unavailable"]), ([], 2))


class SessionTests(unittest.TestCase):
    def test_password_refresh_logout_and_token_redaction(self):
        fixture = {"user": {"id": "a", "app_metadata": {"app_role": "student"}}, "expires_at": 0,
                   "access_token": "private-access-fixture", "refresh_token": "private-refresh-fixture"}

        with patch("services.auth.SupabaseAPI") as transport:
            # Test service inputs and failures without sharing an HTTP client across sessions.
            transport.return_value.__enter__.return_value.request.side_effect = [fixture, fixture, None]
            auth = AuthService(URL, KEY)
            signed_in = auth.sign_in("demo@example.com", "test-fixture")
            self.assertNotIn("private-", repr(signed_in))
            refreshed = auth.refresh_if_needed(signed_in)
            auth.sign_out(refreshed)
            self.assertEqual(transport.call_args.args, (URL, KEY, fixture["access_token"]))
            requests = transport.return_value.__enter__.return_value.request.call_args_list
            self.assertEqual([call.kwargs["params"] for call in requests], [
                {"grant_type": "password"}, {"grant_type": "refresh_token"}, {"scope": "local"},
            ])

    def test_reject_privileged_dashboard_keys(self):
        with self.assertRaises(ValueError):
            DashboardData(URL, "sb_secret_test_fixture")
        with self.assertRaises(ValueError):
            AuthService(URL, "sb_secret_test_fixture")

    def test_transport_uses_bearer_token_and_reports_only_safe_error_details(self):
        def handle(request):
            self.assertEqual(request.headers["authorization"], "Bearer test-user-token")
            self.assertEqual(request.headers["apikey"], KEY)
            return httpx.Response(403, json={"code": "42501", "message": "sensitive-detail"})

        client = httpx.Client
        with patch("services.database.httpx.Client", side_effect=lambda **kw: client(
                **kw, transport=httpx.MockTransport(handle))):
            with SupabaseAPI(URL, KEY, "test-user-token") as api:
                with self.assertRaises(SupabaseError) as failure:
                    api.select("students", "student_id", order="student_id.asc")
        self.assertEqual(failure.exception.code, "42501")
        self.assertNotIn("sensitive-detail", str(failure.exception))


class DashboardTests(unittest.TestCase):
    @patch("services.data_loader.SupabaseAPI")
    def test_student_profile_uses_user_scope_and_preserves_independent_flags(self, connect):
        api = connect.return_value.__enter__.return_value
        result = {"completed_at": "2026-05-20", "offering": {"semester": term(2)}}
        forecast = {"target_semester_id": -3, "displayed_predicted_gpa": 2.2, "projected_cgpa": 2.3,
                    "is_predicted_gpa_at_risk": True, "is_projected_cgpa_at_risk": False}
        api.select.side_effect = [[{"student_id": 1}], [result], [{"semester": term(1)}], [forecast], [term(3)]]
        result = DashboardData(URL, KEY).student_profile(session("student"))
        self.assertEqual(result["latest_forecast"]["target_semester"]["semester_id"], -3)
        self.assertFalse(result["latest_forecast"]["is_projected_cgpa_at_risk"])
        connect.assert_called_once_with(URL, KEY, "test-user-token")
        read_forecast = api.select.call_args_list[3]
        self.assertEqual(read_forecast.kwargs["source_semester_id"], "eq.-2")
        self.assertEqual(read_forecast.kwargs["student_id"], "eq.1")

    @patch("services.data_loader.SupabaseAPI")
    def test_unlinked_student_and_unavailable_forecast(self, connect):
        api = connect.return_value.__enter__.return_value
        api.select.side_effect = [[], [{"student_id": 1}], [], [{"semester": term(1)}], []]
        dash = DashboardData(URL, KEY)
        self.assertIsNone(dash.student_profile(session("student")))
        profile = dash.student_profile(session("student"))
        self.assertIsNone(profile["latest_forecast"])
        self.assertEqual(profile["module_results"], [])

    @patch("services.data_loader.SupabaseAPI")
    def test_teacher_profile_only_queries_assigned_results(self, connect):
        api = connect.return_value.__enter__.return_value
        api.select.side_effect = [[{"student_id": 1}], [{"is_module_at_risk": False}], []]
        dash = DashboardData(URL, KEY)
        profile = dash.teacher_student_profile(session("module_teacher"), 1)
        self.assertEqual(set(profile), {"student", "module_results"})
        self.assertFalse(profile["module_results"][0]["is_module_at_risk"])
        self.assertEqual([call.args[0] for call in api.select.call_args_list], ["students", "module_enrolments"])
        self.assertIsNone(dash.teacher_student_profile(session("module_teacher"), 2))
        with self.assertRaises(PermissionError):
            dash.teacher_roster(session("student"), 1)
