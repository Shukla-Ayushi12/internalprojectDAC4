# Requests between roles

Format: `[From: role] [To: role] [What you need] [Date]`

- [From: Teacher interface (Hannah)] [To: Database and services (Akshaya)] [A function in `services/` that returns the logged-in teacher's students as a table with one row per student and these columns: `student` (display name or anonymised label), `class_name`, `predicted_gpa`, `current_cgpa`, `attendance`, `backlog_subjects`. It must only return students in that teacher's own classes (checked in `services/`, not just on the page). `views/teacher_dashboard.py` will call `render_teacher_dashboard(that_table)`; until then it uses a temporary sample-data stand-in.] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Project lead (Ayushi)] [The dataset has no teachers, classes or semesters, so the teacher page can't filter by class or semester for real yet. This depends on the fourth table (`teachers` or `classes`) being decided. The page's sample preview uses made-up classes A–D.] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Project lead (Ayushi)] [When `app.py` is written, please load the teacher page by calling `render_teacher_dashboard(...)` from `views/teacher_dashboard.py`.] [2026-11-26]
- [From: Teacher interface (Hannah)] [To: Student interface (Kaviya)] [FYI: I created `components/charts.py` with one function, `gpa_distribution`, used by the teacher page. Feel free to add your own chart functions there; please tell me before changing `gpa_distribution`.] [2026-11-26]
