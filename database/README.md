# Development database runbook

Use this guide for a fresh development project or an approved academic data correction. For dashboard access and publishing forecasts, follow the [backend integration guide](../services/README.md).

## Set up a fresh Supabase project

1. Create a development Supabase project in the team's organisation. Keep the database password in an approved password manager. The schema uses PostgreSQL features available in PostgreSQL 15 or later and was verified on hosted PostgreSQL 17.12. [PostgreSQL view options](https://www.postgresql.org/docs/15/sql-createview.html)
2. Enable the Data API for the `public` schema. Keep `app_private` outside the exposed schemas, and leave automatic table grants disabled. [Supabase custom schemas](https://supabase.com/docs/guides/api/using-custom-schemas)
3. Open the development project's SQL Editor as the database owner and run [schema.sql](schema.sql) in full. It wraps creation in a single transaction. Apply it once to a fresh database. Use a reviewed targeted migration for an existing application schema. Verify seven application tables, RLS on each, and the intended grants. [Supabase database and SQL Editor](https://supabase.com/docs/guides/database/overview)

## Set up the fictional cohort

1. Create the three fictional teacher accounts in Supabase Auth and confirm their sign-in status. Use the email values in `TEACHERS` in [seed.py](seed.py). In an approved server-side Auth Admin operation, set `app_metadata` to include `{"app_role": "module_teacher"}`. Store demo passwords securely. The seed resolves these accounts to the teacher UUIDs it needs for module offerings. [Supabase Auth Admin](https://supabase.com/docs/reference/python/admin-api)
2. From the repository root, preview the default cohort and export the owner-run SQL to a new local path. The default SHA-256 and row provenance refer to the checked-in [sample](../data/sample/sample_dataset.csv). The seed accepts `--source` for an alternate compatible CSV and `--seed` for a different generator seed. Keep the same source and seed for an exact rerun.

   ```sh
   .venv/bin/python -B -m database.seed
   .venv/bin/python -B -m database.seed --output /tmp/gpa-demo-seed.sql
   ```

3. Review the generated file and apply it through SQL Editor as the owner of the development database. It contains the prepared data and [finalisation transaction](finalize_demo.sql). PostgreSQL recalculates the summaries, compares them to the generator output, and commits only if they agree.
4. For student sign-in, create confirmed fictional student Auth accounts with `app_metadata.app_role` set to `student`. Link each account ID to the matching `students.auth_user_id`. The seed preserves established student links on an identical rerun. Store demo credentials outside the repository and share through the team’s secure channel.
5. Run the [forecast publisher](../services/README.md#forecast-publishing) after academic finalisation. Confirm the calendar's next-term links and cutoffs, then check the dry-run readiness counts.

The generator uses stable reserved IDs for the demo data. The SQL transaction retains matching rows and rejects conflicting academic data by default. An approved change to existing demo academic values requires a reviewed export with `--allow-corrections`. Corrections advance affected record revisions and can invalidate older forecasts. Reconcile the data first, then use the publisher's explicit correction flow.

## Demo academic policy

| Percentage | Grade | Grade points |
| --- | --- | ---: |
| 80–100 | A | 4.0 |
| 75–<80 | B+ | 3.5 |
| 70–<75 | B | 3.0 |
| 65–<70 | C+ | 2.5 |
| 60–<65 | C | 2.0 |
| 55–<60 | D+ | 1.5 |
| 50–<55 | D | 1.0 |
| 0–<50 | F | 0.0 |

Semester GPA uses the sum of grade points times credits divided by total completed credits for the term. Cumulative CGPA uses the same formula across completed terms. Finalisation uses unrounded quality points and rounds the resulting GPA and CGPA to 12 decimal places. Completed F grades remain in the demo backlog. The fourth semester starts as planned enrolments, with results and GPA-bearing earned credits recorded only for completed modules.

Semester attendance targets the matched sample row's attendance rounded to two decimals. Module attendance values vary to four decimals. Their credit-weighted mean must match the stored two-decimal target, with an unrounded tolerance of 0.00005 percentage points. See the [dataset mapping](../docs/dataset-columns.md#demo-feature-mapping) for provenance.

## Check an import

The default cohort has 24 students, four semesters, 12 modules and offerings, 216 completed results, 72 planned enrolments, and 72 reconciled semester records. The initial publication produced 24 latest forecasts. This read-only query checks the core row totals.

```sql
SELECT
  (SELECT count(*) FROM public.students) AS students,
  (SELECT count(*) FROM public.module_enrolments WHERE completed_at IS NOT NULL) AS completed_results,
  (SELECT count(*) FROM public.module_enrolments WHERE completed_at IS NULL) AS planned_enrolments,
  (SELECT count(*) FROM public.semester_records WHERE record_revision = reconciled_revision) AS reconciled_records,
  (SELECT count(*) FROM public.forecasts) AS forecasts;
```

Run account visibility checks through signed-in student and teacher sessions. The owner connection in SQL Editor is for administration and data verification. The [integration guide](../services/README.md#verification-and-ui-handoff) lists the hosted access checks.
