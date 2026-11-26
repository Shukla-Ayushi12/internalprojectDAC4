# Team workflow

Run commands from the repository root. Use [TEAM.md](TEAM.md) to identify owners and coordinate changes that affect another workstream. Agent-specific instructions live in [AGENTS.md](AGENTS.md).

## Before you change anything

1. Check the branch and working tree with `git status --short` so you can distinguish existing work from your changes.
2. Read the [project specification](PROJECT.md) and the guide for your task in the [repository README](../README.md).
3. Reuse the project `.venv`. Coordinate changes to dependencies, model artifacts, or shared UI with their respective owners.

## Review and handoff

1. Keep changes within your workstream or agree on shared changes with the relevant owner. Record open cross-workstream requests in the team’s request log.
2. Run the relevant local checks and record what they cover. Document hosted checks separately and identify any pending application-level verification.
3. Review `git diff --check`, `git diff`, and `git status --short`. The status also shows new files that have not been staged. Check that raw data, processed data, local environments, credentials, and private records stay out of the handoff.
4. Share the reviewed change through the team’s Git workflow with the files affected, the verification performed, and any follow-up dependencies. The project lead coordinates the merge.

## Supabase changes

Use the [database runbook](../database/README.md) for deployment or demo data changes. Review schema changes in `database/schema.sql` first and use an approved migration for an existing database. Test dashboard permissions with signed-in student and teacher sessions. Coordinate hosted changes with the database owner and obtain approval before changing credentials or deleting data.
