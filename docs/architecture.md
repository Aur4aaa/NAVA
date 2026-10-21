# Architecture and authorization

NAVA is a Django modular monolith using server-rendered templates, local static assets, SQLite, private filesystem storage, and Waitress. Progressive browser behavior enhances forms and dashboards without a separate frontend build or API dependency. The initial deployment contains one organization.

## Application structure

| Component | Responsibility |
|---|---|
| `config/settings.py` | Local runtime, timezone, data path, session/CSRF configuration, private media location |
| `workspace/models.py` | Relational records, version series, owner/classification metadata, constraints |
| `workspace/permissions.py` | Role presets, object visibility, ownership checks, approval authority |
| `workspace/services.py` | Business transitions, approvals, revisions, snapshots, activity events |
| `workspace/forms.py` and `views.py` | Validated input, permission-filtered pages/downloads/exports |
| `workspace/catalog.py` | Independent framework reference catalog and original summaries |
| `workspace/templates` and `static` | Responsive interface, data-driven dashboards, relationship views |
| `scripts` | Setup, Waitress launcher, verified backup and restore |

## Traceability and versions

`ScopeVersion` anchors the scope. Interested parties and `Requirement` records connect relevant obligations to reference controls. `RiskAssessmentVersion` records its methodology version and scope, affected assets/processes, linked obligations, scoring rationale, and control mappings. `TreatmentPlan` and `RiskAcceptance` record decisions separately from control implementation.

`FrameworkVersion`, `RequirementReference`, and `ControlReference` describe a separately versioned catalog. Management-system requirements are separate from Annex A applicability decisions. `ControlImplementation` keeps applicability, implementation, evidence, and effectiveness distinct; `SoAVersion` captures a reviewed snapshot. `DocumentVersion` and `EvidenceVersion` retain version lineage and access metadata. Evidence file checksums detect byte changes without establishing truth or authenticity.

Tasks, approvals, audits, findings, corrective actions, management reviews, certification records, and audit packages preserve links to the decisions and versions they concern. An approval or frozen snapshot is not inferred from the existence of an attachment. Certification-body decisions are separate from internal readiness and Stage 1/Stage 2 tracking.

Versioned records use a stable series UUID, version number, and previous-version link; visible identifiers are type-prefixed database IDs. A revision counter supports optimistic concurrency checks. Approved/frozen versions require a new revision for changes. Foreign-key protection and application transition rules preserve referenced history. A local database administrator can bypass application rules; the audit trail is not cryptographically tamper-proof.

## Role presets

Permissions are enforced in server code. A hidden menu or button is not the authorization boundary. Internal visibility below remains subject to classification, explicit sharing, ownership, and active-account checks.

| Preset | Business access | Edit/create authority | Approval authority |
|---|---|---|---|
| System administrator | No automatic business visibility | Account/configuration administration | None unless separately assigned a business approval role |
| Manager | Internal records and permitted confidential records | Coordinates business records; frozen records require revision | Evidence review authority; governance/document/risk approval requires a separate applicable role |
| Approver | Permitted internal/shared records | No general editing authority from this preset alone | Governance and authorized business approvals; assigned document approver restrictions apply |
| Risk owner | Permitted internal/shared records | Assigned risk assessments, treatments, acceptances, tasks, evidence | Treatment and residual-risk decisions for the assigned risk when the service's conditions are met |
| Control owner | Permitted internal/shared records | Assigned controls, documents, evidence, tasks, and applicable operational records | Assigned evidence reviews; no general governance approval |
| Document approver | Permitted internal/shared records | Assigned document/task/evidence records | Documents assigned to that approver, subject to workflow validation |
| Internal auditor | Permitted internal/shared records | Assigned audits, findings, corrective actions, evidence, tasks | Assigned evidence reviews; closure/independence conditions are evaluated separately |
| External auditor | Explicitly shared evidence/packages only, before access expiry | Read only | None |
| Contributor | Permitted internal/shared records | Assigned tasks and evidence | None |
| Viewer | Permitted internal/shared records | Read only | None |

The presets are implemented with Django groups and server-side policy. Group membership is explicit; superuser status is not a business-approval shortcut. Full administrator-configurable arbitrary permission policy is a later refinement. Any broadening of external-auditor visibility must preserve default denial and file/export checks.

## File and export boundary

Evidence is stored beneath the private data directory, outside public static assets. Downloads require authenticated object authorization; guessing a filename or record ID does not bypass it. Uploaded bytes are retained by version, with file type/size restrictions and attachment handling. There is no integrated malware scanner. Permission filtering also applies to search and exported data; spreadsheet exports escape formula-leading cell values. Approved review/SoA snapshots are preserved, while displayed/exported derivatives recheck access to embedded source records and links. Revoking source access does not rewrite the retained original snapshot.

## Frozen audit-package access

Audit packages contain exact versions of approved scoped records and selected evidence, together with a manifest, a traceability index, and recorded omissions. The package is frozen after generation and cannot be silently relinked or regenerated. Generation checks selected evidence scope, source permissions, current record revision, and file integrity. The package classification reflects included material.

An explicit package share grants its frozen metadata. Download also requires current permission to each included evidence version; external auditors need future-expiry grants on both the package and its evidence. Package and evidence checksums are rechecked when downloaded. These are integrity checks, not authenticity guarantees or cryptographic approval signatures.

## PostgreSQL migration path

The initial settings intentionally configure SQLite only. To migrate for shared use:

1. Back up and restore a staging copy with the current code version; verify evidence first.
2. Add a pinned supported PostgreSQL driver and explicit settings selected from secure environment configuration.
3. Provision a private database/user, TLS where required, and least-privilege grants. Apply Django migrations into an empty database.
4. Transfer application/auth data using an audited Django data migration or reviewed dump/load procedure that preserves primary keys, content-type references, version links, approvals, and timestamps. Exclude/reconcile generated content types and permission records deliberately; do not blindly duplicate them.
5. Retain private media files at a matching protected storage path and verify every evidence reference/hash.
6. Run the permission, concurrency, versioning, export, and backup/restore suite against PostgreSQL; perform a representative user journey and count reconciliation.
7. Configure HTTPS, host restrictions, a production service account, and database-aware backups; cut over only after verification.

PostgreSQL execution and migration are deferred, not validated by the current SQLite tests. SQLite-specific operational backup scripts must be replaced with coordinated PostgreSQL and evidence backups before that cutover.
