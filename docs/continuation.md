# Delivery checklist and continuation plan

This delivery is a runnable **Milestone 1 foundation**, with frozen audit packages, recurring task generation, and recovery features from Milestone 2. It does not implement the full depth of every item in the [product brief](product-brief.md).

## Implemented

- Django 5.2.18 with SQLite, private local files, authentication, explicit role presets, and a loopback Waitress launcher.
- Responsive dark interface with saved-record dashboards, a 12-stage roadmap, risk matrix, traceability map, paginated registers, forms, search, settings, and approval actions.
- Versioned scopes, climate relevance/rationale, interested parties, obligations, basic clause/control gap assessments, risk methodology and assessment versions, treatment plans, and residual-risk acceptances.
- All 93 Annex A reference identifiers and seven separate management-system areas, with original summaries and independent catalog releases. **Official-source verification remains pending.**
- Control applicability, implementation, evidence coverage, and recorded effectiveness kept separate; approved/published SoA snapshots preserve decisions.
- Document review/approval/publication and new revisions; evidence uploads, private downloads, SHA-256 checks, human review/acceptance, expiry, and immutable file versions.
- Owned tasks, blocking dependencies, recurrence generation, append-only application events, optimistic revision checks, and authorized transitions.
- Internal/external audit records, findings, corrective-plan approval, independent effectiveness closure, management-review snapshots, and separate certification-decision tracking.
- Permission-filtered CSV, XLSX, PDF, and frozen ZIP audit packages. Timed external-auditor sharing requires explicit package access and separate access to included evidence files.
- Setup/start scripts, stopped-instance SQLite/file backups, manifest validation, safe restore, overwrite preservation, and an explicit fictional demonstration workspace.

Asset, supplier, and objective models exist and are used in the demo. Dedicated lifecycle registers and the wider operational workflows around them are not delivered user-facing modules yet. Full arbitrary permission-policy customization is also deferred; the current policy uses explicit role presets and record access assignments.

## Validation record

On **21 October 2026**, Linux / Python **3.12.14**:

```sh
.venv/bin/python manage.py test tests --noinput --verbosity 1
```

**76 tests passed; no skipped or expected-failure tests.** Django system checks reported no issues; `makemigrations --check --dry-run` found no schema drift and `pip check` found no dependency conflicts. The suite contains 32 domain tests, 12 HTTP tests, 13 export/package tests, five catalog tests, five demo tests, and nine recovery tests. Permission-denial and not-found log messages during these tests are expected assertions of access boundaries.

Additional Linux integration checks passed:

- **Browser journey against Waitress:** sign-in, dashboard, registers/settings, traceability, task create/start/complete, evidence upload/review/download with exact-byte comparison, CSV/XLSX/PDF downloads, search, and the mobile menu/Escape interaction. No JavaScript errors or horizontal overflow at 1440 px and 390 px viewport widths. The repeatable driver is `tests/browser_smoke.py`; it accepts an explicitly created demo username, a private password file, and a Chromium executable.
- **Live recovery:** backed up the demonstration database and private files, restored into a new directory, and verified all 11 archived files by manifest hash plus SQLite integrity checks.
- **Fresh installation:** copied source into a new path containing spaces, with no virtual environment, database, or secret; `python scripts/setup.py --no-admin` installed the pinned packages, migrated, and seeded 93 reference controls. The resulting database had zero users, organizations, or business records. `python scripts/start.py --port 8001` launched Waitress via system Python; health and login requests returned HTTP 200.
- **Repeatability:** `scripts/setup.py --skip-install --no-admin` preserved the demonstration records and refreshed the installation.

Windows execution is not locally verified. The repository includes Ubuntu/Windows GitHub Actions jobs, whose outcome must be checked on the actual run.

## Requested acceptance criteria

“Tested” below describes the implemented behavior demonstrated by automated checks, not a claim of external audit acceptance or exhaustive production qualification.

| # | Requested behavior | Delivery evidence and limits |
|---:|---|---|
| 1 | Approve and revise scope without rewriting history | Tested in domain and HTTP workflows; original approved version retained and impact-review task created. |
| 2 | Link interested-party obligations to risks/controls | Tested relational chain through party, requirement, risk, and control. |
| 3 | Assess using a methodology version and assign treatment | Tested methodology approval, explicit scores, preserved version references, and treatment links. |
| 4 | Authorize treatment and residual-risk acceptance | Tested role/owner authority, expiry, current score, and treatment belonging to the same risk version. |
| 5 | Produce SoA and report omissions | Tested all-reference export, missing applicability/justification/owner checks, and frozen approved decisions. |
| 6 | Upload/review evidence and preserve earlier bytes | Tested file validation, human review before acceptance, replacement versions, and checksums. |
| 7 | Publish documents only after authorized approval | Tested approval/publication transitions and preservation of prior content. |
| 8 | Block guessed restricted evidence URLs/search/exports | Tested anonymous and unauthorized direct URLs, form choices, search, downloads, CSV/XLSX/PDF, and frozen-snapshot derivatives. No inline untrusted preview is provided. |
| 9 | Corrective-action chain and independent closure | Tested root cause, approved plan, implementation/current evidence, independent verifier, closure rationale, and reopening. |
| 10 | Preserve management-review snapshot/minutes | Tested approved snapshot preservation and current permission filtering of embedded source material. |
| 11 | Freeze audit-pack versions and evidence | Tested exact source versions/bytes, manifest checks, sharing expiry/revocation, and source/archive integrity failures. |
| 12 | Separate Stage 1, Stage 2, certification decision | Tested distinct audit types and evidence requirements for a recorded granted decision. Demo decision remains pending. |
| 13 | Actionable expired evidence/overdue work | Tested dashboard and filtered record links. Broader notifications and recurring review policies remain deferred. |
| 14 | Avoid duplicate setup/recurrence records | Tested catalog, role, demo, and recurring-task idempotence. Existing records are preserved. |
| 15 | Back up/restore DB and evidence intact | Eight recovery tests cover roundtrip, hashes, paths with spaces, locks, archive safety, and overwrite preservation. A live demo backup and new-directory restore also passed manifest and SQLite checks. |
| 16 | Validated CSV import without silent partial writes | **Deferred.** Export is implemented; no import button or pretend import workflow is exposed. |
| 17 | Reject concurrent stale edits | Tested optimistic revision checks, stale HTTP submissions, frozen version protection, and frozen relation mutation guards. Full load/concurrency qualification is deferred. |
| 18 | New installation using documented process | Clean Linux setup in a path with spaces and Waitress start/health/login checks passed; Windows commands and CI jobs supplied. Windows 11 operational acceptance is still required. |

## Remaining scope, in order

1. **Standards verification.** Retrieve official edition/amendment sources, review original summaries against licensed material, and publish a separately versioned verified catalog. Add granular subclause assessments and catalog-update impact planning.
2. **Complete operational registers.** Add asset/supplier lifecycle interfaces, competence/training, access reviews, incidents, changes, restoration/continuity exercises, structured objectives, and acknowledgments. Reuse the existing ownership, evidence, task, approval, and event services.
3. **Imports and collaboration.** Add atomic CSV preview/validation/duplicate handling, bulk assignment, comments, notifications, saved filters, and board/calendar views. Extend recurring tasks into explicit recurring-review policies.
4. **Assurance depth.** Add audit programs, interviews/sampling/working papers, richer management-review inputs, configurable finding severity, lifecycle retention/deletion controls, and surveillance/renewal maintenance. Current certification records require evidence for a granted decision; they do not automate certification-body arrangements.
5. **Operational qualification.** Run Windows 11 fresh setup, stop/restart, file-lock contention, Unicode/space-containing paths, large uploads, backup/restore, updates/rollback, and browser accessibility tests. Verify GitHub CI outcomes separately from this Linux validation.
6. **Shared deployment.** Implement the documented PostgreSQL migration path, coordinated database/file recovery, HTTPS/service deployment, stronger configurable permissions, shared-service rate limiting, malware scanning, and monitoring.
7. **Optional services.** Add AI drafting, email/calendar adapters, SSO, or external storage only after explicit provider configuration and data-sharing controls. None are enabled by this delivery.

No deployment, certificate, certification-body approval, Windows execution, or PostgreSQL operation is implied by a passing software test. Preserve the working local workflow and a verified backup while implementing the next complete increment.
