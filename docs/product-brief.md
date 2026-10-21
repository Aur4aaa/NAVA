# Codex build prompt: ISMS implementation and certification workspace

You are a senior Python application architect, full-stack developer, security engineer, and experienced ISO/IEC 27001 implementer. Build a usable application that guides an organization from defining its Information Security Management System (ISMS) scope through implementation, certification preparation, external audit tracking, and continual improvement.

Working name: ISMS Certification Workspace. Make the name configurable.

## 1. Work instructions

This is an implementation request. Inspect the repository and its instructions, make a practical implementation plan, then build and test the application. Do not stop at a proposal, screen mockups, or a database schema.

If a functioning project exists, preserve its working behavior and conventions. Do not replace it without a concrete reason. If the repository is empty, scaffold the project.

Ask questions only for decisions that would materially change the architecture or risk data loss. Otherwise use the defaults below, record assumptions, and proceed. Do not assume API keys, existing infrastructure, purchased services, or a preconfigured database.

Work in complete, testable increments. Maintain a checklist of implemented, tested, and deferred features. Never present placeholder buttons, mock statistics, hard-coded success messages, or unimplemented integrations as working features. If the full scope cannot be completed in one execution, leave a runnable increment and an exact continuation plan; do not claim the full product is complete.

## 2. Product outcome and operating defaults

Help an ISMS manager answer:
- What must we do next, who owns it, and when is it due?
- What remains incomplete, unapproved, unsupported by evidence, or overdue?
- Which risks led to each selected control?
- Which policies, operational records, and tests demonstrate implementation and effectiveness?
- Can an auditor follow the trail from scope to risk to treatment to evidence?
- What changed since the last review or audit?

Default operating environment:
- Windows 11, initially on one host PC using a local web browser.
- A supported Python version compatible with all selected dependencies; document the exact tested version.
- Django with server-rendered templates and progressive enhancement such as HTMX, if suitable. Prefer a modular monolith over microservices.
- SQLite for the initial local deployment, with a documented PostgreSQL migration path for later shared use.
- Private local file storage for evidence; authentication and authorization still apply on localhost.
- A production-capable Windows-compatible application server for normal use; do not make Django's development server the normal operational launcher.
- No mandatory Docker, Redis, cloud account, paid API, or AI service.
- Bind to 127.0.0.1 by default. Shared-network deployment requires deliberate configuration, HTTPS, and deployment hardening.
- Configurable organization timezone; default Asia/Kuala_Lumpur. Store timestamps consistently and display local time.
- Single organization initially, with multiple departments, locations, business processes, and versioned ISMS scopes. Do not claim multi-tenant isolation unless implemented and tested.

The application supports certification preparation and recordkeeping. It does not issue certification, guarantee compliance, or replace the certification body's decision.

## 3. Standards model and content accuracy

Use ISO/IEC 27001:2022 with Amendment 1:2024 as the initial baseline. Confirm applicable editions and amendments from official sources before implementing the catalog; record source, edition, verification date, and content provenance.

Represent:
- Clauses 4–10 as management-system requirements.
- Annex A's 93 reference controls across organizational, people, physical, and technological themes.
- ISO/IEC 27002 as guidance, clearly distinguished from certification requirements.
- The climate-related context and interested-party considerations introduced by the 2024 amendment.

Do not copy a paid standard's full text into seed data, templates, or reports. Use control identifiers, original concise summaries, and permitted metadata. Support organization-supplied licensed material without exposing it to unauthorized users. Mark unverified mappings explicitly rather than inventing authoritative wording.

Do not allow users to treat clauses 4–10 as optional Annex A controls. Annex A applicability is determined through risk treatment and relevant requirements, with justified exclusions. Support controls outside Annex A where necessary.

Version the framework catalog independently of organizational implementation data. A framework update must preserve historical assessments, approvals, Statement of Applicability (SoA) versions, and audit snapshots.

## 4. Roles and authorization

Provide configurable permissions with useful presets:
- System administrator: accounts, configuration, backups; no automatic business approval authority.
- ISMS manager: coordinates scope, assessments, controls, documents, evidence, and audits.
- Top management/authorized approver: approves assigned governance decisions and resources.
- Risk owner: assesses assigned risks and approves treatment plans and residual risk where authorized.
- Control/process owner: implements assigned controls and supplies evidence.
- Document reviewer/approver: reviews and approves assigned documents.
- Internal auditor: performs authorized audits and records findings.
- External auditor: time-limited, read-only access to explicitly shared audit material.
- Staff contributor: completes assigned tasks, acknowledges policies, submits permitted evidence.
- Read-only management viewer.

Enforce authorization on the server for pages, APIs, direct file links, search, previews, bulk actions, and exports. Menu visibility is not an access control. Restrict confidential evidence separately where needed. Record auditor independence and potential conflicts; do not silently treat self-review as independent auditing.

## 5. Guided lifecycle and workflow engine

Provide a certification roadmap with these stages:
1. Initiation, context, and scope.
2. Leadership, governance, and objectives.
3. Gap assessment and implementation planning.
4. Risk assessment and treatment.
5. SoA and control implementation.
6. Document approval and operational evidence collection.
7. Monitoring, competence, and effectiveness evaluation.
8. Internal audit and corrective action.
9. Management review.
10. Stage 1 external audit preparation and follow-up.
11. Stage 2 external audit preparation and follow-up.
12. Certification decision recording and ongoing maintenance.

Stages can overlap and iterate. Avoid a rigid one-way wizard. Each stage needs owners, tasks, dependencies, required outputs, approvals, due dates, evidence, blockers, and a clear completion explanation.

Distinguish normative requirements from suggested project milestones. Readiness rules are transparent internal checks, not certification-body rules. Authorized overrides require a reason and leave an audit record; overrides must never fabricate missing evidence or approvals.

A “Next actions” view should prioritize blocking dependencies, overdue reviews, unaccepted risks, missing evidence, and upcoming audit deadlines. Support recurring tasks, reassignment, comments, activity history, and in-app notifications.

## 6. Context and scope module

Capture organization profile, internal/external issues, interested parties and relevant requirements, organizational boundaries, sites, processes, technologies, information, outsourced services, interfaces, and dependencies.

Maintain a requirements register for legal, regulatory, contractual, customer, and internal obligations. Record source, jurisdiction, applicability rationale, owner, review date, and linked controls/evidence. Do not invent applicable laws from an organization name or country.

Provide a structured scope builder that produces a readable scope statement with boundary rationale and exclusions. Distinguish scope boundary decisions from Annex A exclusions.

Record whether climate change is relevant to the ISMS context and any relevant interested-party requirements, with rationale and review history. Do not automatically require unrelated environmental controls.

Scope versions require review and approval. Material scope changes trigger impact reviews of assets, risks, SoA, documents, and audit coverage rather than silently replacing historical scope.

## 7. Leadership, governance, and objectives

Provide:
- ISMS policy drafting, approval, publication, and review.
- Roles, responsibilities, decision authorities, and RACI assignments.
- Management commitment, budget/resource requests, and decisions.
- Measurable security objectives with owner, baseline, target, measurement method, reporting frequency, and linked actions.
- Communication plan covering what, when, to whom, by whom, and how.
- Planned-change records with purpose, consequences, resources, responsibilities, and review.

Templates are editable starters, not automatic evidence of implementation.

## 8. Asset, process, supplier, and dependency registers

Track information assets, systems, applications, services, processes, locations, and relevant suppliers. Include owner, custodian, scope membership, classification, criticality, confidentiality/integrity/availability needs, lifecycle state, and dependencies.

Use process- and scenario-based risks as well as asset-based risks; do not require every risk to belong to a hardware asset.

Support validated CSV import with preview, row-level errors, duplicate detection, and explicit confirmation before committing changes. Provide export and bulk assignment.

Supplier records include service, information access, criticality, applicable obligations, assessments, contracts/evidence, review dates, and linked risks. This is an ISMS register, not a procurement system.

## 9. Gap assessment

Provide versioned assessments covering clauses and Annex A, scoped to a selected ISMS scope. Record status, assessor, assessment date, rationale, evidence, findings, owner, priority, and remediation tasks.

Separate “not assessed,” “partially implemented,” “implemented,” and “effectiveness verified.” Missing evidence must not produce a compliant result. Applicability is a separate decision from implementation status.

Display clause and control gaps separately. Preserve assessment history and support comparisons without overwriting earlier results.

## 10. Risk assessment and treatment

Provide a configurable, versioned methodology:
- Likelihood and impact scales with written criteria.
- Default 5-by-5 matrix, clearly identified as an application default rather than an ISO requirement.
- Defined acceptance criteria and approval authorities.
- Initial, current, and target residual risk distinguished clearly.
- Review frequency and triggers.

Risk fields include scenario, causes/threats/vulnerabilities where relevant, consequences, affected processes/assets, existing controls, owner, assessment date, scoring rationale, treatment decision, and evidence.

Support avoid, modify/mitigate, share/transfer, and retain/accept decisions, with contextual explanation. Linking a control must not automatically reduce a risk score.

Treatment plans include selected controls, actions, owner, resources/cost estimate, deadlines, progress, expected residual risk, and risk-owner approval. Record explicit residual-risk acceptance, its justification, approver, date, and review/expiry date.

Preserve approved assessment snapshots. A methodology change must not silently recalculate historical results. Notify owners of overdue risk reviews and expired acceptances.

## 11. SoA and control implementation

Provide a versioned SoA covering all 93 Annex A controls plus organization-specific controls.

For each control, capture:
- Identifier, framework edition, and original summary.
- Applicability decision.
- Inclusion or exclusion justification.
- Linked risks and other applicable requirements.
- Implementation status and explanation.
- Owner and planned actions.
- Linked policies, procedures, evidence, and effectiveness tests.
- Last review and next review.
- Approval and version history.

Support many-to-many relationships among risks, controls, obligations, and evidence. Keep applicability, implementation, and effectiveness separate.

Publish approved SoA snapshots and export to XLSX and PDF. Flag unjustified exclusions, unassigned applicable controls, broken mappings, expired evidence, and changes awaiting approval.

## 12. Document control and evidence

Documents:
- Stable ID, title, type, owner, classification, version, reviewers, approvers, effective date, and review date.
- Draft → review → approved → published → superseded/archived workflow.
- Comments, change summaries, approval history, acknowledgments, and access restrictions.
- Immutable approved versions; revisions create new versions.
- No silent replacement of a published policy.

Evidence:
- Files, external references, structured records, screenshots, and test results.
- Owner, source, collection date, period covered, classification, linked requirements/controls/risks, reviewer, review status, retention rule, and expiry/review date.
- Immutable file versions with checksums, upload metadata, and replacement history.
- A checksum helps detect byte changes; do not present it as proof of authenticity or truth.
- Distinguish uploaded, reviewed, accepted for a purpose, expired, and rejected.
- Evidence relevance and sufficiency require human judgment; one upload is not automatic control effectiveness.

Allow evidence reuse across mappings while keeping the coverage period and context visible. Preserve files used by frozen audit packages. Retention holds must prevent deletion; authorized deletion outside holds must leave an appropriate metadata trail.

Store files outside publicly served directories. Enforce authenticated downloads, safe filenames, upload size/type restrictions, and safe rendering. Never execute uploads or render untrusted HTML directly. If malware scanning is unavailable, show that limitation accurately and avoid claiming uploads were scanned.

## 13. Operational records and effectiveness

Provide lightweight workflows for:
- Training, competence, attendance, assessments, and policy acknowledgments.
- Access reviews and joiner/mover/leaver evidence.
- Incident records, lessons learned, and related corrective actions.
- Change reviews and approvals.
- Backup restoration exercises and continuity exercise records.
- Supplier reassessments.
- Control testing and monitoring.

Each workflow should reuse shared owners, tasks, evidence, approvals, and audit history instead of creating disconnected registers.

Metrics include definition, data source, owner, target, period, result, interpretation, and follow-up. Missing data must display as missing, not zero or success. Do not claim to have run technical tests merely because someone uploaded a report.

## 14. Internal audit and corrective action

Support risk-based audit programs, audit plans, scope, criteria, auditor assignments, independence checks, schedules, interviews, sampling, working papers, evidence, and reports.

Findings should identify the applicable requirement, observed condition, objective evidence, classification, owner, and deadline. Severity schemes are configurable and distinguished from the external certification body's classifications.

Corrective action workflow:
1. Record finding/nonconformity.
2. Record immediate correction/containment where appropriate.
3. Analyze root cause.
4. Plan and approve corrective action.
5. Implement and attach evidence.
6. Independently verify effectiveness where required by the organization's process.
7. Close or reopen with rationale.

Do not close an issue solely because an attachment exists or a task is marked done. Preserve reopened cases and closure history.

## 15. Management review

Build an editable management-review pack from current records. Cover status of prior actions, context and interested-party changes, objectives and performance, monitoring results, audit results, nonconformities and corrective actions, relevant feedback, risk assessment/treatment status, and improvement opportunities.

Capture attendance, agenda, discussion, decisions, resource needs, required ISMS changes, action owners, deadlines, and approved minutes. Freeze the reviewed data snapshot so later edits do not rewrite what management considered.

## 16. External audit and certification tracking

Provide an audit workspace for certification-body details, intended scope, schedules, requests, document submissions, auditor access, Stage 1 findings, Stage 2 findings, and follow-up actions.

Separate:
- Internal readiness assessment.
- External audit completion.
- Auditor recommendation, if provided.
- Certification body's recorded decision.

Record certification only from an authorized user's entry backed by supporting documentation. Store certificate number, issuer, certified scope, standard edition, issue/expiry dates, certificate attachment, status, and entered-by history. Handle suspension, withdrawal, scope changes, and renewal.

Track surveillance and recertification milestones using the actual certificate and certification-body arrangements. Do not invent binding deadlines from a generic schedule.

## 17. Audit packs, reporting, and search

Generate permission-filtered audit packs containing:
- A selected scope and framework edition.
- Scope statement and governance documents.
- Approved risk methodology, assessments, treatment plans, and acceptances.
- Approved SoA.
- Selected documents and operating evidence.
- Internal audit reports and corrective actions.
- Management review records.
- A traceability index and manifest.

Freeze included versions, generation time, period covered, and selection criteria. Include checksums and explicitly identify omitted/restricted content. Use permission checks when creating and downloading packages. Redaction should produce a derivative without altering the original.

Provide PDF management reports, XLSX registers/SoA, CSV data export, and ZIP evidence packs with readable paths and an index. Guard spreadsheet exports against formula injection.

Search by ID, title, owner, scope, control, risk, status, and date. Search results must respect access restrictions.

## 18. Dashboard and user experience

Create a professional, responsive interface with accessible forms, clear typography, keyboard support, helpful empty states, and readable tables. Avoid excessive animations.

Provide:
- Executive dashboard: major risks, objectives, overdue actions, upcoming audits, decisions needed.
- ISMS manager dashboard: roadmap, blockers, approvals, gaps, and evidence coverage.
- Owner dashboard: assigned tasks, reviews, controls, and risks.
- Auditor workspace: authorized evidence and frozen audit materials.

Use drill-down links from every metric to its underlying records. Show numerator, denominator, exclusions, and snapshot date for percentages. Keep document completion, control implementation, evidence coverage, and effectiveness verification as separate metrics.

If there is an overall readiness indicator, label it as an internal planning estimate, explain its calculation, and show blocking conditions. Never display “100% certified” from completed tasks.

Provide list/board/calendar views where useful, filters, saved views, progress details, clear validation errors, and context-sensitive guidance. “Why is this blocked?” should explain dependencies and link to the necessary action.

## 19. AI assistance: optional later enhancement

The core application must work without AI or API keys.

An optional provider adapter may help draft policy text, summarize evidence, suggest risk scenarios, propose mappings, and explain gaps. Keep suggestions separate from approved records.

Require human review before adopting AI output. AI must not approve documents, accept risk, invent evidence, close findings, or declare certification. Show source references and uncertainty when available.

Keep credentials server-side, outside source control and logs. Do not send confidential documents to external providers without an explicit administrator-controlled data-sharing configuration and clear user awareness. Treat document content as untrusted input and prevent embedded instructions from invoking tools or changing permissions.

If this enhancement is not implemented, document it as deferred and do not add a fake working chat interface.

## 20. Data model and engineering requirements

Model explicit entities for Organization, ScopeVersion, InterestedParty, Requirement, Asset/Process, Supplier, FrameworkVersion, RequirementReference, ControlReference, GapAssessment, RiskMethodologyVersion, RiskAssessmentVersion, TreatmentPlan, RiskAcceptance, SoAVersion, ControlImplementation, DocumentVersion, EvidenceVersion, EvidenceLink, Task, Approval, Audit, Finding, CorrectiveAction, ManagementReview, MetricResult, CertificationRecord, AuditPack, and ActivityEvent.

Use relational foreign keys and explicit mapping tables for important traceability paths. Include stable IDs, timestamps, actor information, scope context, and version references where appropriate.

Implement:
- Database constraints and migrations.
- Transactional approval and publishing operations.
- Concurrency protection against lost updates.
- Idempotent recurring-task generation.
- Pagination and appropriate indexes.
- Clear service-layer rules for transitions and permissions.
- Safe archive behavior with protection for approved/audited records.
- Structured logging without secrets or full sensitive attachments.
- Friendly error pages with diagnostic identifiers.
- Health checks that do not expose sensitive configuration.

Record security and business events such as login failures, permission changes, approvals, downloads/exports, version publication, archive/delete actions, and certification updates.

Make audit events append-only through application permissions. Describe honestly that a local machine or database administrator may still modify storage; do not claim an immutable or tamper-proof ledger without implementing and validating that property.

## 21. Installation, operation, and recovery

Deliver:
- README with exact tested prerequisites and Windows commands.
- A pinned dependency specification and example environment configuration without secrets.
- Setup script that creates a virtual environment, installs dependencies, applies migrations, and guides secure first-admin creation.
- Start script with preflight checks for missing settings, database state, writable paths, and port conflicts.
- Explicit stop/restart instructions.
- Backup and restore commands covering database, evidence files, version metadata, and required configuration.
- Consistent backups that avoid mismatched database/file versions.
- Restore verification and clear overwrite confirmation.
- Update procedure with backup and migration guidance.
- Troubleshooting for dependency failures, missing modules, migration errors, locked database, ports, permissions, and HTTP 500 errors.

Scripts must support paths containing spaces, fail clearly, and be safe to rerun. Do not require administrator installation unless unavoidable and documented. Do not claim Windows execution was tested if only Linux testing was possible.

Keep demonstration data separate and visibly labeled. Production setup starts clean; demo seeding is explicit. Do not embed fixed default administrator credentials.

## 22. Delivery order

Deliver in this order while preserving a runnable application:

Milestone 1 — End-to-end foundation:
Authentication, roles, scope/versioning, framework references, basic gap assessment, risk methodology and register, treatment plan, SoA, document/evidence versions, approvals, tasks, activity trail, basic internal audit/finding workflow, management-review records, external-audit tracker, and usable exports.

Milestone 2 — Operational depth:
Complete supplier/assets registers, training and operational records, control effectiveness, recurring reviews, refined permissions, frozen audit packs, certification maintenance, dashboards, imports, backup/restore, and complete Windows installation flow.

Milestone 3 — Optional enhancements:
AI assistance, email/calendar integrations, advanced analytics, SSO, shared PostgreSQL deployment, and external storage adapters. Implement external services only when configured; never send messages or publish records through unconfigured integrations.

Document the exact milestone reached and remaining scope. Prioritize the complete traceable workflow over decorative screens.

## 23. Acceptance criteria and tests

Implement meaningful tests for permission boundaries, state transitions, traceability, and data integrity. At minimum demonstrate:

1. Create and approve a scope; revise it without altering the earlier approved version.
2. Record an interested-party obligation and link it to a risk or control.
3. Assess a risk with a recorded methodology version and assign treatment.
4. Require authorized approval for a treatment plan and residual-risk acceptance.
5. Produce an SoA with justified applicability decisions; report omissions.
6. Upload and review evidence; preserve original bytes when a new version is added.
7. Publish a document only through authorized approval.
8. An unauthorized user cannot retrieve restricted evidence via a guessed direct URL, search, preview, or export.
9. Record an internal audit finding, root cause, corrective action, effectiveness check, and closure.
10. Generate management-review minutes and preserve the reviewed snapshot.
11. Generate an audit pack that resolves links to the intended frozen versions.
12. Track Stage 1 and Stage 2 separately from the certification decision.
13. Expired evidence and overdue reviews appear in actionable dashboards.
14. Re-running setup or scheduled task generation does not duplicate critical records.
15. Back up and restore a sample organization with its evidence files intact.
16. Imported invalid rows produce actionable errors without partial silent corruption.
17. Concurrent editing does not silently overwrite an approved record.
18. A new installation starts successfully using the documented process.

Use a coherent fictional organization for the demo. Include one full example chain:
scope → obligation/process → risk → treatment → control/SoA → policy → operating evidence → effectiveness check → audit finding → corrective action → management review → certification tracking.

Test core logic, HTTP authorization, uploads/downloads, exports, and one representative end-to-end user journey. Report actual commands, results, and environment limitations. Do not claim external audit acceptance or certification from software tests.

## 24. Final handover

Provide:
- What is implemented and how to launch it.
- Architecture and data-model summary.
- Role/permission matrix.
- Standards mapping approach and source register.
- Installation, administration, backup/restore, and user guidance.
- Test results and known limitations.
- Demonstration workflow.
- Prioritized remaining backlog.
- Any decisions needed from me.

Begin by inspecting the repository, stating reasonable assumptions, and implementing Milestone 1. Continue through the authorized scope as far as the execution environment allows while maintaining truthful progress and a working application.
