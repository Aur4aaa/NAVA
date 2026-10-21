# Using the ISMS workspace

## Start with an organization and named responsibilities

Sign in with an account created during setup. Open **Settings** to name the organization and set its timezone. A system administrator can create accounts and assign the role presets. Administration alone grants no business approval authority; use an explicit Manager, Approver, or other appropriate role. See the [role matrix](architecture.md#role-presets).

The sidebar opens the main registers. Related-register links within a page lead to requirements, parties, methodologies, treatment, acceptances, SoA versions, findings, corrective actions, and certification records. Search respects the same record permissions as lists and downloads. Each dashboard metric links to its source records.

## Create a traceable working record

1. In **Context & scope**, add a scope statement, boundaries, owner, climate-relevance decision, and rationale. Save the draft, submit it for review, then have an authorized Approver approve it.
2. Add an interested party and a sourced requirement. Record why the requirement applies; the application does not infer laws or obligations from your organization name.
3. In **Risk register → Risk methodology**, review the default 5 × 5 criteria and acceptance authority, then submit and approve the methodology. Add a risk scenario using that methodology, record explicit scoring rationale, and link relevant requirements. Approve the assessment before its treatment.
4. Add a treatment plan with owner, decision, actions, selected controls, and target risk. An assigned authorized risk owner or Approver approves the plan. Acceptance is a separate decision requiring a reason, explicit current score, and future expiry. A control link does not reduce a recorded score.
5. In **Controls & SoA**, record each control's applicability and justification, owner, implementation, and supporting policies/evidence. Applicability, implementation, and effectiveness are separate fields. The SoA lists missing decisions and blocks approval until its required justifications and assignments are complete.
6. Create controlled documents as drafts. Submit, approve, and publish through the displayed authorized actions. To change an approved version, use **Create revision**; the original remains available.

An outdated edit is rejected rather than silently replacing a newer save. Refresh the record, inspect the other changes, and reapply the intended edit. Decisions and state transitions appear in the record's activity history.

## Evidence, review, and access

**Evidence library** accepts files or external references. Record the coverage period, source, owner, classification, expiry, and intended links. A file upload begins as uploaded evidence; an authorized reviewer records relevance and sufficiency before accepting it for a stated purpose. Acceptance does not certify the truth of the file or automatically verify a control's effectiveness.

Downloads are private attachments and are checked against the stored SHA-256 value. Uploading a replacement creates a new version with its own bytes and checksum. Expired evidence appears in actionable dashboard filters and does not count toward current accepted evidence coverage. The application does not provide malware scanning or execute technical tests described in uploaded reports.

Managers can use the **Manage record access** section to grant or revoke explicit access, including on a frozen record. This changes access assignments, not approved content. External auditors can read only explicitly shared evidence and audit packages with a future expiry. Confidential evidence is visible to managers as well as specifically authorized users; restricted evidence requires owner/creator/explicit access. Share related evidence separately from its policy, risk, or control.

## Tasks, audits, and decisions

Use **Action center** for owners, due dates, required outputs, dependencies, and evidence requirements. Completing a task needs a recorded output explanation and any required accepted evidence; unfinished dependencies block completion. Recurring task instances are generated with:

```powershell
.\.venv\Scripts\python.exe manage.py generate_recurring_tasks --username your-manager
```

The command is idempotent for each due recurrence date. It does not install an automatic scheduler.

In **Audit workspace**, select Internal, Stage 1, Stage 2, or another audit type explicitly. Internal audit completion requires a report and a named independent auditor/conflict assessment. Findings link the applicable reference to observed conditions and evidence. A corrective action records correction, root cause, plan, implementation, and effectiveness. The plan needs approval; closure needs current accepted evidence, an independent verifier, and a rationale. Reopening retains the earlier history.

Management-review records hold attendees, minutes, decisions, resources, and actions. Approval freezes the reviewed data snapshot; later source changes do not rewrite it. Restricted source material is filtered when another user reads a derivative view. The certification tracker separately records the certification body's documented decision. A granted decision requires supporting documentation and certificate details; task completion and completed audits do not imply certification.

## Reports and frozen audit packages

Registers offer CSV, XLSX, and PDF exports using the current accessible records and filters. Spreadsheet exports neutralize formula-leading values. SoA exports use the approved frozen decision rows when available; a draft export is a live working view.

To generate a package, open **Audit packages**, create a draft for an approved scope, select the framework and the evidence versions to include, and record the coverage period and selection criteria. **Generate frozen package** retains the selected evidence bytes and exact record snapshots in a ZIP with a manifest and traceability index. Unapproved, inaccessible, and unselected material is identified as omitted; external references are not downloaded. Coverage dates describe the selection and do not silently filter linked records.

Sharing a package grants its included frozen record metadata. Every included evidence file also requires current separate evidence access on download. Review the package contents before sharing it. Subsequent source revisions do not rewrite a generated package; create another package for a later review period.

## Meridian Cloud demonstration walkthrough

Run the explicit demo setup described in the [README](../README.md#optional-demonstration-workspace), using a separate data directory and an existing account you control. The workspace and files are labeled fictional. Supporting example accounts have unusable passwords until a local administrator deliberately sets one.

Follow this existing chain:

1. Open **Cloud platform & corporate operations** in Context & scope. Inspect its approved statement, boundaries, and climate assessment.
2. Open the **Enterprise customers** party and **Customer access and recovery commitments** requirement through related-register links.
3. Open **Privileged access retained after role changes** in Risk register. Follow the methodology and requirement links, then **Reduce privileged-access review gaps** in Risk treatment.
4. Inspect the A.5.18 control implementation and **Statement of applicability — baseline**. Compare applicability with implementation and effectiveness fields.
5. Read the published **Identity and access management procedure** and download **Quarterly access review — owner sign-off**. The file itself states that it is demonstration evidence.
6. In Audit workspace, follow **Access governance internal audit**, **Role-change trigger missing from access reviews**, and **Add and verify role-change review trigger**. Inspect the plan approval, independent retest, and closure history.
7. Open **ISMS implementation management review** and compare the frozen snapshot with current records. Stage 1 and Stage 2 remain distinct planned audits; **Certification decision — awaiting external assessment** remains pending.
8. Use **Traceability map** to select the access-risk scenario and navigate its connected records. Inspect the expired supplier evidence and overdue actions from the dashboard.
9. Generate a new demo audit package from the approved scope, select example evidence, and examine its manifest/index. Exercise a document revision or evidence replacement to see the earlier version remain intact.

The dashboard figures come from these stored example records. They illustrate recordkeeping and navigation, not actual security testing, organizational compliance, or certification.
