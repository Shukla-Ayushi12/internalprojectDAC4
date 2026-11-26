# Team roles and handoff

This file is the source of truth for task ownership. Paths are relative to the repository root. See [PROJECT.md](PROJECT.md) for the architecture and [WORKFLOW.md](WORKFLOW.md) for collaboration.

| # | Member | Workstream | Files and folders owned | Current status |
| --- | --- | --- | --- | --- |
| 1 | Ayushi | Project lead and integration | `app.py`, `requirements.txt`, whole-repo review | App shell, integration, and deployment pending |
| 2 | Ayushi | Data and model | `data/`, `model/` | Cleaned sample, trained model, and evaluation available |
| 3 | Akshaya | Database and services | `database/`, `services/` | Implemented and verified in development. Integration handoff ready. |
| 4 | Kaviya | Student interface | `views/student_dashboard.py` | Streamlit integration pending |
| 5 | Hannah | Teacher interface | `views/teacher_dashboard.py` | Streamlit integration pending |
| 6 | Yuki / Kimi | Testing, privacy, and ethics | `tests/`, `docs/ethics*` | Browser-level acceptance, fairness, and privacy review pending |
| 7 | Yuan Ling | Documentation and presentation | `docs/` | Project reference available. Report, slides, and demo script pending. |

Kaviya and Hannah share `components/` and coordinate shared chart and theme changes. For a cross-owner change, discuss the request with the owner and record it in the team’s request log when follow-up is needed. With six team members, the testing and documentation workstreams can be combined as in the original team plan.

## Handoff by workstream

### Data and model

- [x] Document the source data columns and provide a checked-in sample.
- [x] Supply the cleaning, training, and evaluation scripts and the saved artifact.
- [x] Record MAE, R², and baseline comparisons in [Model Results](../docs/model-results.md).
- [x] Document the [demo feature mapping](../docs/dataset-columns.md#demo-feature-mapping) used by the backend.
- Full raw and cleaned files stay local to the model workflow.

### Database and services

- [x] Deploy the seven-table Supabase schema with grants and RLS in the development project.
- [x] Generate and reconcile the fictional cohort. Verify that an identical seed rerun preserves rows and revisions.
- [x] Implement inference and forecast publication. Verify the 24 latest forecasts and an unchanged publisher rerun.
- [x] Provision and link demo Auth identities. Verify student self-access and teacher module isolation through live sessions.
- [x] Supply the [dashboard integration contract](../services/README.md) and [database runbook](../database/README.md).
- [ ] Share the backend changes through the team’s Git review workflow and arrange secure access to demo credentials.

### Student interface

- [ ] Use the signed-in session and the backend's `student_profile()`.
- [ ] Show actual history and the latest next-semester forecast, with separate GPA and CGPA warnings.
- [ ] Provide an unavailable state and label forecasts as estimates. Review any proposed personal model explanations with the model workstream.

### Teacher interface

- [ ] Use the backend's assigned offerings, roster, and scoped student profile methods.
- [ ] Show each offering's results, attendance, and intervention flags, including pending and unflagged students.
- [ ] Add module and semester filters and roster sorting as needed.

### Testing, privacy, and documentation

- [ ] Verify the integrated Streamlit sign-in, session lifecycle, display states, and role switching with development accounts.
- [ ] Write the privacy and ethics notes and assess model suitability beyond the synthetic demo.
- [ ] Prepare the meeting notes, final report, slides, and demo script.

## Dependencies

- The Streamlit shell and both dashboards can integrate using the [backend interfaces](../services/README.md).
- Application-level acceptance depends on the integrated pages and access to development demo accounts.
- The saved model and checked-in sample support local verification. Access to the full dataset is needed to rerun model training and evaluation.
- The project lead reviews and merges the workstreams and coordinates the app deployment.
