# AGENTS.md: Instructions for AI Coding Agents (Codex, Claude Code, etc.)

You are helping a team member who is **not a programmer**. Assume they cannot read code, debug errors, or use git without guidance.

## First, every session
1. Read `PROJECT.md` (what we're building) and `TEAM.md` (who owns what).
2. Ask the user: "Which team member are you, and which role in TEAM.md?" if it isn't already stated.
3. Work **only** inside the folder that person owns. Do not edit other folders. If a change is needed elsewhere, write it down in `/docs/requests.md` for the owner instead.

## How to talk to the user
- Plain language, no jargon. Explain what you did and why in 2-3 sentences.
- Before big changes, say what you're about to do and ask for a yes.
- When something breaks, explain it simply and fix it yourself where possible.
- Never ask the user to edit code by hand.

## Working rules
- Keep changes small and easy to review.
- Run the code/tests after changes and report whether they worked.
- Do not install large new libraries or change the tech stack without asking the project lead.
- Do not delete files you didn't create.
- Follow `WORKFLOW.md` for saving and sharing work.

## Project setup (read `PROJECT.md` for the full layout)
- The app is **Streamlit only**. There is no FastAPI and no separate API server.
- Data is stored in **Supabase** (cloud Postgres). Only files in `services/` may talk to it. Pages in `views/` must never query the database directly.
- Pages arrange things on screen. Chart code goes in `components/`, data/database/model code goes in `services/`.

## Data and privacy (strict)
- Never commit raw data (`data/raw/`) or any real student data, names, IDs, or grades. Only `data/sample/` is committed.
- Never put passwords, API keys, or secrets in code or committed files. Supabase keys go in `.streamlit/secrets.toml` (never committed) and in the deployment platform's secrets settings.
- The interface must always show that predictions are estimates.
- A student may only ever see their own data. A teacher may only see their own classes.

## Database rules
- `database/schema.sql` is the source of truth for the tables (`students`, `subjects`, `grades`, and a fourth table still to be decided). Update it first whenever a table changes.
- Only the Database and services role changes tables. Others ask through `/docs/requests.md`.
- Never drop, truncate, or delete tables or rows without the user and the project lead confirming first.
- Keep Row Level Security turned on for every table.

## Model rules (for the data/model workstream)
- Target: the semester GPA we predict. Model: XGBoost.
- Fix a random seed so results can be reproduced.
- Save the trained model to `/model/artifacts/` and record its metrics in `/docs`.
- Do not use features that would leak the answer (e.g. the grades of the semester being predicted).
- Read the real dataset columns from the Kaggle CSV header. Do not guess column names.

## Code style
- Python, clear names, short comments explaining *why*.
- One responsibility per file where possible.

## When unsure
Stop and ask the user, or note the question in `/docs/requests.md`. Don't guess on anything involving student data.