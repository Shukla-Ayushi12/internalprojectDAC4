# Requests between roles

Format: `[From: role] [To: role] [What you need] [Date]`

- [From: Teacher interface (Hannah)] [To: Database and services (Akshaya)] [DONE: the teacher page now uses `teacher_modules()` and `teacher_roster()` from `feat/supabase-gpa-backend`. Thanks!] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Project lead (Ayushi)] [When `app.py` is written, after sign-in and `auth.refresh_if_needed(...)`, load the teacher page with `render_teacher_dashboard(data, session)` from `views/teacher_dashboard.py`, where `data` is a `DashboardData` and `session` has role `module_teacher`. The page's own sign-in form is preview-only.] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Database and services (Akshaya)] [Please share demo teacher sign-in details securely (not in Git), plus the dev project URL and publishable key for `.streamlit/secrets.toml`, so I can test the teacher page against the real development database.] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Student interface (Kaviya)] [FYI: `components/charts.py` has one function, `score_distribution` (module scores 0–100% with a flag line), used by the teacher page. Feel free to add your own chart functions there; please tell me before changing `score_distribution`.] [2026-11-26]
