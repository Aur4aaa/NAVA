"""Explicit, isolated demonstration data; never run by production setup."""
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from workspace import catalog, models as m
from workspace.permissions import ensure_roles
from workspace.services import (
    approve_record,
    create_record,
    log_event,
    transition_record,
    update_record,
    upload_evidence,
)

DEMO_NAME = "Meridian Cloud"
DEMO_MARKER = "demo.seeded"
DEMO_USERS = {
    "demo.amina": ("Amina", "Rahman", ("Approver", "Document approver")),
    "demo.daniel": ("Daniel", "Lee", ("Risk owner", "Approver")),
    "demo.sara": ("Sara", "Tan", ("Control owner",)),
    "demo.isaac": ("Isaac", "Wong", ("Internal auditor",)),
}


class Command(BaseCommand):
    help = (
        "Create the fictional Meridian Cloud demonstration in an empty database. "
        "Requires an existing --user account; never installs default credentials."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            required=True,
            help="Existing active account that will receive the Manager role for this demo.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            manager = user_model.objects.get(username=options["user"], is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError("Create an active account first, then pass its username with --user.") from exc

        organization = m.Organization.objects.first()
        if (
            organization
            and organization.is_demo
            and m.Organization.objects.count() == 1
            and m.ActivityEvent.objects.filter(action=DEMO_MARKER, object_id=organization.pk).exists()
        ):
            self.stdout.write("The demonstration already exists. All records, files, and user edits were preserved.")
            return
        if organization:
            raise CommandError("Demo seeding requires an empty organization database. Use a separate NAVA_DATA_DIR.")
        for model in apps.get_app_config("workspace").get_models():
            if issubclass(model, m.Record) and model.objects.exists():
                raise CommandError("Existing business records were found. Demo seeding will not modify them; use a separate NAVA_DATA_DIR.")
        if user_model.objects.filter(username__in=DEMO_USERS).exists():
            raise CommandError("Reserved demo usernames already exist. Use a new demonstration database.")

        self.written_files = []
        try:
            with transaction.atomic():
                self.seed(manager)
        except Exception:
            # Database rollback cannot roll back storage writes. Only remove files
            # created during this invocation; pre-existing data was rejected above.
            for storage, filename in self.written_files:
                storage.delete(filename)
            raise
        self.stdout.write(self.style.SUCCESS(
            "Meridian Cloud demonstration created: 93 control decisions, 8 risks, "
            "4 documents, 8 evidence files, and the linked audit journey."
        ))
        self.stdout.write(
            f"Sign in using the existing account {manager.username}. "
            "Fictional supporting accounts have unusable passwords. "
            "No certification decision has been granted."
        )

    def seed(self, manager):
        today = timezone.localdate()
        date = lambda days: today + timedelta(days=days)
        groups = ensure_roles()
        manager.groups.add(groups["Manager"])
        demo_people = {}
        for username, (first, last, roles) in DEMO_USERS.items():
            person = get_user_model()(username=username, first_name=first, last_name=last)
            person.set_unusable_password()
            person.save()
            person.groups.add(*(groups[role] for role in roles))
            demo_people[username] = person
        approver = demo_people["demo.amina"]
        risk_owner = demo_people["demo.daniel"]
        control_owner = demo_people["demo.sara"]
        auditor = demo_people["demo.isaac"]
        self.manager = manager

        organization = m.Organization.objects.create(
            name=DEMO_NAME,
            timezone="Asia/Kuala_Lumpur",
            is_demo=True,
            description=(
                "Fictional SaaS organization for a NAVA demonstration. Every policy, risk, "
                "evidence file, assessment, person, and audit entry is illustrative. "
                "These records are not evidence for any real organization."
            ),
        )
        call_command("seed_framework", stdout=self.stdout)
        framework = m.FrameworkVersion.objects.get(
            name=catalog.FRAMEWORK_NAME,
            edition=catalog.FRAMEWORK_EDITION,
            catalog_release=catalog.CATALOG_RELEASE,
        )
        controls = {control.identifier: control for control in framework.controls.all()}

        def refs(*identifiers):
            return [controls[identifier] for identifier in identifiers]

        def create(model, **fields):
            fields.setdefault("owner", manager)
            return create_record(manager, model, **fields)

        def approve(record, by=approver, publish=False):
            transition_record(manager, record, "submit")
            approve_record(by, record, reason="Fictional demonstration: reviewed the stated content and recorded this decision.")
            if publish:
                transition_record(by, record, "publish")
            return record

        scope = approve(create(
            m.ScopeVersion,
            title="Cloud platform & corporate operations",
            statement=(
                "The fictional ISMS covers the design, development, operation, and support of "
                "Meridian Cloud's customer collaboration platform, including supporting "
                "corporate systems and staff in Kuala Lumpur."
            ),
            boundaries="Cloud production and staging, corporate identity, employee devices, engineering, support, and management.",
            exclusions="Customer-owned devices and customer network administration are outside the organizational boundary; supplier interfaces remain assessed.",
            locations="Kuala Lumpur office and authorized remote work locations.",
            processes="Software delivery, identity administration, customer support, incident response, supplier oversight.",
            technologies="Managed cloud hosting, identity provider, source repositories, endpoint management, and backup services.",
            interfaces="Cloud hosting provider, payment processor, support contractors, and customer administrators.",
            climate_relevance="relevant",
            climate_rationale="Flooding and power interruption could affect office access and remote-working availability. Continuity arrangements are reviewed; this does not imply unrelated environmental controls.",
            review_date=date(180),
        ))
        methodology = approve(create(
            m.RiskMethodologyVersion,
            title="Meridian 5 × 5 assessment method",
            description="Illustrative internal method: likelihood × impact. These numerical scales are an application default, not an ISO requirement.",
            acceptance_threshold=6,
            acceptance_authority="Named risk owner with explicit approval authority; higher risks require top-management approval.",
        ))
        party = create(
            m.InterestedParty, scope=scope, title="Enterprise customers", party_type="customer",
            expectations="Protect customer information, restrict access, and provide a documented service recovery approach.",
            climate_requirements="Customer resilience questionnaire asks how site disruption is addressed.",
            review_date=date(150),
        )
        obligation = create(
            m.Requirement, scope=scope, party=party,
            title="Customer access and recovery commitments",
            source="Fictional Meridian enterprise service agreement, schedule 3.",
            requirement_type="contractual",
            jurisdiction="Contractual example only; no applicable law is inferred.",
            applicability_rationale="Applies to the in-scope hosted service and personnel with customer-data access.",
            controls=refs("A.5.15", "A.5.18", "A.8.13"),
            review_date=date(120),
        )
        process = create(
            m.Asset, scope=scope, title="Customer collaboration platform",
            asset_type="service", criticality="high", custodian="Platform engineering",
            description="Fictional managed SaaS service and associated customer information.",
            confidentiality=4, integrity=4, availability=4,
        )
        create(
            m.Supplier, scope=scope, title="Northstar Hosting — fictional supplier",
            service="Managed hosting and resilient storage for the demonstration service.",
            information_access="Infrastructure administration; encrypted customer data storage.",
            criticality="high", review_date=date(30), owner=risk_owner,
        )

        risk_specs = [
            ("Privileged access retained after role changes", 4, 4, 3, 4, "A.5.18", "Stale group memberships may permit unauthorized administrative actions.", -3),
            ("Customer data exposed through cloud configuration", 4, 5, 4, 5, "A.8.9", "A configuration change could expose a customer-data storage boundary.", 14),
            ("Restore failure during a service outage", 4, 4, 3, 4, "A.8.13", "An incomplete backup or untested restoration could extend an outage.", 21),
            ("Supplier disruption affects customer support", 3, 4, 3, 3, "A.5.22", "A critical service provider could fail to meet recovery commitments.", 30),
            ("Phishing leads to an account takeover", 4, 4, 3, 3, "A.6.3", "A staff member could approve a malicious sign-in or disclose credentials.", 35),
            ("Unreviewed production change causes downtime", 3, 4, 2, 3, "A.8.32", "An inadequately reviewed deployment could interrupt critical service.", 45),
            ("Lost device exposes cached business information", 3, 3, 2, 2, "A.8.1", "A missing employee laptop could disclose locally cached records.", 60),
            ("Flooding interrupts office-based coordination", 2, 4, 1, 3, "A.5.30", "An office outage could delay incident coordination unless remote arrangements work.", 75),
        ]
        risks = []
        for title, likelihood, impact, current_likelihood, current_impact, identifier, scenario, review_days in risk_specs:
            risk = create(
                m.RiskAssessmentVersion, scope=scope, methodology=methodology, title=title,
                owner=risk_owner, scenario=scenario,
                causes="Fictional assessment workshop: process inconsistency, service dependencies, and human error.",
                consequences="Loss of confidentiality, service disruption, contractual impact, or recovery effort.",
                existing_controls="Existing procedures and technical safeguards were discussed in the fictional assessment.",
                likelihood=likelihood, impact=impact,
                current_likelihood=current_likelihood, current_impact=current_impact,
                scoring_rationale="The fictional risk workshop explicitly assessed these scores using the recorded methodology. Control links do not calculate or reduce the score.",
                assessment_date=date(-14), review_date=date(review_days),
                requirements=[obligation], assets=[process], controls=refs(identifier),
            )
            approve(risk, by=risk_owner)
            risks.append(risk)
        treatment = approve(create(
            m.TreatmentPlan, title="Reduce privileged-access review gaps",
            risk=risks[0], owner=risk_owner, decision="modify",
            rationale="Make access recertification accountable and verify timely removal of obsolete privileges.",
            actions="Inventory privileged groups, obtain owner attestations, remove stale access, and sample the next review cycle.",
            resources="Security lead and platform team: two working days per review cycle.",
            due_date=date(7), target_likelihood=2, target_impact=4, controls=refs("A.5.18", "A.8.2"),
        ), by=risk_owner)
        approve(create(
            m.RiskAcceptance, title="Accept limited lost-device residual exposure",
            risk=risks[6], owner=risk_owner, accepted_score=risks[6].current_score,
            rationale="Fictional decision: current encrypted-device arrangements and response capacity support retaining the explicitly recorded score of 4 until the next review.",
            expires_on=date(90),
        ), by=risk_owner)

        document_specs = [
            ("Information security policy", "policy", ("A.5.1",), "Management establishes an information security program, assigns responsibilities, and reviews objectives. Staff report suspected incidents and follow approved handling requirements."),
            ("Identity and access management procedure", "procedure", ("A.5.15", "A.5.16", "A.5.18", "A.8.2"), "Owners approve access appropriate to roles. Privileged memberships are reviewed quarterly. Role changes trigger removal of obsolete access, with reviewer decisions and exceptions retained."),
            ("Backup and restoration procedure", "procedure", ("A.8.13", "A.5.30"), "Platform staff verify backup jobs, record exceptions, and exercise restoration against an agreed scope. The service owner evaluates recovery results and owns follow-up actions."),
            ("Supplier assurance procedure", "procedure", ("A.5.19", "A.5.20", "A.5.22"), "Service owners assess supplier dependencies, record information access, review commitments, and investigate changes in service delivery or assurance."),
        ]
        documents = []
        for index, (title, kind, mapped, body) in enumerate(document_specs):
            document = create(
                m.DocumentVersion, scope=scope, title=title, owner=control_owner,
                document_type=kind, body=f"FICTIONAL DEMONSTRATION DOCUMENT — not an adopted organizational policy.\n\n{body}",
                change_summary="Initial demonstration version.",
                reviewer=manager, approver=approver, effective_date=date(-30),
                review_date=date(150), controls=refs(*mapped),
            )
            if index < 3:
                approve(document, publish=True)
            else:
                transition_record(manager, document, "submit")
            documents.append(document)

        evidence_specs = [
            ("Quarterly access review — owner sign-off", ("A.5.15", "A.5.16", "A.5.18", "A.8.2"), "Fictional sample: 12 privileged identities reviewed; two stale memberships removed; owner sign-off recorded.", 60),
            ("Restoration exercise — customer workspace", ("A.8.13", "A.5.30"), "Fictional exercise: representative workspace restored in 44 minutes; sampled records reconciled; follow-up owned by platform engineering.", 90),
            ("Security awareness attendance and assessment", ("A.6.3",), "Fictional training record: 42 staff attended; assessment scores and follow-up training recorded.", 120),
            ("Endpoint encryption inventory sample", ("A.8.1", "A.8.24"), "Fictional sample: managed endpoints had encryption and screen lock enabled; one loan device excluded with an open follow-up.", 60),
            ("Approved production change sample", ("A.8.32", "A.8.25", "A.8.29"), "Fictional change: reviewer approval, rollback plan, test results, and deployment outcome linked to release MC-014.", 90),
            ("Access review corrective-action retest", ("A.5.18", "A.8.2"), "Fictional independent retest: ten changed-role accounts sampled in the subsequent review; all obsolete privileges removed within the defined window.", 90),
            ("Policy communication acknowledgment sample", ("A.5.1", "A.6.2"), "Fictional acknowledgment sample: the approved information security policy was communicated and 12 sample acknowledgments were inspected.", 180),
            ("Supplier assurance report — renewal required", ("A.5.19", "A.5.20", "A.5.22"), "FICTIONAL EXPIRED REFERENCE: prior supplier assessment has passed its review date. Obtain updated assurance before relying on it for the current period.", -5),
        ]
        evidence_records = []
        for index, (title, mapped, body, expires) in enumerate(evidence_specs):
            file_body = (
                f"MERIDIAN CLOUD — FICTIONAL DEMONSTRATION EVIDENCE\n"
                f"Title: {title}\nCollected: {date(-20).isoformat()}\n"
                "No actual technical test was performed by this application.\n\n"
                f"{body}\n\nThis file demonstrates recordkeeping only.\n"
            )
            evidence = upload_evidence(
                manager, ContentFile(file_body.encode("utf-8"), name=f"meridian-example-{index + 1:02d}.txt"),
                title=title, scope=scope, owner=control_owner,
                description="Fictional demonstration record. Human relevance and sufficiency must be evaluated in a real implementation.",
                source="Explicit Meridian Cloud demonstration seed",
                collected_on=date(-20), period_start=date(-90), period_end=date(-14),
                expires_on=date(expires), retention_rule="Demo only. A real retention schedule requires organizational approval.",
                controls=refs(*mapped), risks=[risks[0]] if index in (0, 5) else [],
                classification="restricted" if index == 3 else "internal",
                allowed_users=[approver, auditor] if index == 3 else [],
            )
            self.written_files.append((evidence.file.storage, evidence.file.name))
            transition_record(manager, evidence, "review_evidence", reason="Fictional review: checked the stated sample, coverage period, and limitations.")
            if expires > 0:
                transition_record(manager, evidence, "accept_evidence", reason="Accepted solely as an illustrative demonstration record for its stated purpose; this is not real organizational evidence.")
            evidence_records.append(evidence)

        evidence_by_control = {}
        for evidence in evidence_records:
            for control_id in evidence.controls.values_list("pk", flat=True):
                evidence_by_control.setdefault(control_id, []).append(evidence)
        documents_by_control = {}
        for document in documents:
            for control_id in document.controls.values_list("pk", flat=True):
                documents_by_control.setdefault(control_id, []).append(document)
        risk_by_control = {}
        for risk in risks:
            for control_id in risk.controls.values_list("pk", flat=True):
                risk_by_control.setdefault(control_id, []).append(risk)
        exclusions = {
            "A.7.4": "Fictional scope decision: no organization-operated building surveillance system; landlord arrangements and physical access risks are separately assessed. Reassess if facilities change.",
            "A.7.12": "Fictional scope decision: office structured cabling is managed by the building operator; interface responsibilities are recorded. No internal data-center cabling is in scope.",
            "A.8.30": "Fictional scope decision: software development is performed by employees; there is no outsourced development engagement. Reassess before such an engagement.",
        }
        implementations = {}
        for index, control in enumerate(controls.values()):
            linked = evidence_by_control.get(control.pk, [])
            current_accepted = [item for item in linked if item.status == "accepted" and not item.is_expired]
            excluded = control.identifier in exclusions
            implementation_status = (
                "not_assessed" if excluded else
                "implemented" if current_accepted or index % 10 < 6 else
                "partial" if index % 10 < 9 else "planned"
            )
            implementation = create(
                m.ControlImplementation, scope=scope,
                title=control.title, control=control, owner=control_owner,
                applicability="excluded" if excluded else "applicable",
                justification=exclusions.get(control.identifier, "Fictional applicability decision: supports the in-scope service, organizational responsibilities, or assessed information security risks; confirm against licensed material before real use."),
                implementation_status=implementation_status,
                implementation_notes="Demonstration owner assessment recorded. Evidence coverage and effectiveness are tracked independently from this implementation status.",
                effectiveness="effective" if current_accepted else "not_tested",
                effectiveness_notes="Fictional human review of the linked sample and its stated purpose; no technical testing was performed by the application." if current_accepted else "",
                tested_on=date(-10) if current_accepted else None,
                review_date=date(60 + index % 8 * 10),
                evidence=linked, documents=documents_by_control.get(control.pk, []),
                risks=risk_by_control.get(control.pk, []),
                requirements=[obligation] if control in refs("A.5.15", "A.5.18", "A.8.13") else [],
            )
            implementations[control.identifier] = implementation
        for reference in framework.requirements.all():
            create(
                m.GapAssessment, scope=scope,
                title=f"Clause {reference.identifier} — initial assessment",
                requirement=reference, implementation_status="partial",
                rationale="Fictional initial assessment identifies remaining governance and operating-record work. This is not a compliance determination.",
                owner=manager, evidence=[evidence_records[6]], assessment_date=date(-12),
            )
        soa = approve(create(
            m.SoAVersion, title="Statement of applicability — baseline",
            scope=scope, framework=framework,
            description="Fictional reviewed applicability baseline. Catalog source verification remains pending; implementation and effectiveness are separate from applicability.",
        ), publish=True)

        internal = create(
            m.Audit, scope=scope, title="Access governance internal audit",
            audit_type="internal", owner=manager, auditor=auditor,
            scheduled_date=date(-10), criteria="Approved access procedure and the recorded A.5.18 applicability decision.",
            independence_notes="Fictional auditor Isaac Wong does not administer the reviewed access controls or own the corrective action.",
            report="Fictional sample identified a missing review trigger for a role change; corrective action and a subsequent sample are linked.",
            evidence=[evidence_records[0], evidence_records[5]],
        )
        transition_record(manager, internal, "start")
        finding = create(
            m.Finding, title="Role-change trigger missing from access reviews",
            audit=internal, control=controls["A.5.18"], owner=control_owner,
            condition="The fictional sample found two privileges retained after a role change.",
            objective_evidence="Quarterly review and corrective-action retest records describe the sampled accounts and decisions.",
            severity="minor", due_date=date(-2), evidence=[evidence_records[0]],
        )
        corrective = create(
            m.CorrectiveAction, title="Add and verify role-change review trigger",
            finding=finding, owner=control_owner, due_date=date(-2),
            correction="Removed the two obsolete privileges recorded in the fictional sample.",
            root_cause="The role-change process notified HR but did not assign identity-review ownership.",
            plan="Add an owner-approved role-change checklist, train responsible staff, and independently sample the next review.",
            implementation_notes="Fictional checklist released and responsibilities communicated.",
            effectiveness_notes="Independent fictional retest sampled ten changed-role accounts; all obsolete privileges were removed within the defined window.",
            evidence=[evidence_records[5]],
        )
        transition_record(approver, corrective, "approve_plan", reason="Fictional management approval of the root-cause-based plan and resources.")
        transition_record(manager, corrective, "start")
        transition_record(auditor, corrective, "close", reason="Fictional independent retest supports closure for the recorded sample. Continue recurring review.")
        transition_record(auditor, finding, "close", reason="The corrective action is independently verified and closed; retain the sample and review history.")
        transition_record(manager, internal, "complete")

        task_specs = [
            (1, "Approve scope and context boundaries", -25, "complete", "high"),
            (2, "Publish information security policy", -20, "complete", "high"),
            (3, "Record the initial clause assessment", -15, "complete", "medium"),
            (4, "Approve priority risk treatment", -12, "complete", "high"),
            (5, "Publish the applicability baseline", -10, "complete", "high"),
            (6, "Attach access-review evidence", -9, "complete", "medium"),
            (7, "Review the restoration exercise results", -7, "complete", "medium"),
            (8, "Verify access-review corrective action", -2, "complete", "high"),
            (9, "Hold management review and assign decisions", 3, "in_progress", "high"),
            (10, "Assemble the Stage 1 evidence package", 10, "in_progress", "high"),
            (11, "Confirm Stage 2 sampling arrangements", 35, "draft", "medium"),
            (12, "Record the certification body's decision", 70, "draft", "medium"),
            (4, "Reassess cloud configuration exposure", -3, "in_progress", "critical"),
            (6, "Renew supplier assurance evidence", -5, "in_progress", "high"),
            (5, "Confirm privileged-access control owner", -1, "draft", "high"),
            (6, "Review the supplier assurance procedure", 4, "in_progress", "medium"),
            (7, "Run the next access recertification", 18, "draft", "medium"),
            (10, "Resolve missing evidence coverage", 8, "draft", "high"),
        ]
        tasks = []
        for index, (stage, title, due, state, priority) in enumerate(task_specs):
            task = create(
                m.Task, scope=scope, title=title, stage=stage,
                owner=[manager, control_owner, risk_owner][index % 3],
                description="Fictional project milestone. Completion explains a stored output, not certification readiness.",
                priority=priority, due_date=date(due),
                required_output="Retain the relevant decision, operating record, or reviewed output and identify follow-up work.",
                requires_evidence=index == 5,
                evidence=[evidence_records[0]] if index == 5 else [],
                recurrence_days=90 if index == 16 else None,
                dependencies=[tasks[8]] if index == 9 else [tasks[9]] if index == 10 else [],
            )
            if state in {"complete", "in_progress"}:
                transition_record(manager, task, "start")
            if state == "complete":
                transition_record(manager, task, "complete", reason="Fictional project output is recorded in the linked scope, policy, assessment, SoA, or audit workflow.")
            tasks.append(task)

        review = create(
            m.ManagementReview, scope=scope, title="ISMS implementation management review",
            meeting_date=date(-1), owner=manager,
            attendees="Amina Rahman, Daniel Lee, Sara Tan, Isaac Wong, and the ISMS manager (fictional participants).",
            agenda="Prior actions; context and climate relevance; risk and treatment; objectives; internal audit and corrective action; evidence gaps; upcoming external audit preparation.",
            minutes="The fictional meeting reviewed the frozen records, accepted the access-review corrective-action outcome, and identified configuration and supplier-assurance gaps for follow-up.",
            decisions="Prioritize the cloud configuration assessment and supplier evidence renewal. Retain separate Stage 1 and Stage 2 preparations. No certification decision has been made.",
            resource_needs="Allocate two platform-engineering days and one supplier-management day.",
            actions=[tasks[12], tasks[13], tasks[17]],
        )
        approve(review)
        for kind, days, title in (
            ("stage1", 14, "Stage 1 — documentation readiness review"),
            ("stage2", 45, "Stage 2 — operating effectiveness assessment"),
        ):
            create(
                m.Audit, scope=scope, title=title, audit_type=kind,
                scheduled_date=date(days), owner=manager,
                criteria="Fictional planned review against the selected scope and recorded framework baseline.",
                certification_body="Demonstration only — no real certification body appointed",
                independence_notes="External auditor appointment and any conflict assessment remain to be confirmed.",
            )
        create(
            m.CertificationRecord, scope=scope, title="Certification decision — awaiting external assessment",
            decision="pending", owner=manager,
            certified_scope=scope.statement,
            description="Tracking entry only. Stage 1 and Stage 2 have not been completed and no certificate has been issued.",
        )
        create(
            m.MetricResult, scope=scope, title="Privileged-access review timeliness",
            definition="Fraction of sampled changed-role accounts reviewed within the agreed internal window.",
            data_source="Fictional corrective-action retest: ten sampled accounts.",
            target="100% of the defined sample", period=f"{date(-30)} to {today}",
            result=100, unit="percent",
            interpretation="Illustrative sample result; does not establish organization-wide effectiveness.",
        )
        m.EvidenceLink.objects.create(
            evidence=evidence_records[0], requirement=obligation, control=controls["A.5.18"],
            risk=risks[0], purpose="Fictional access-review sample links customer commitments, risk treatment, and control implementation.",
            created_by=manager,
        )
        log_event(manager, DEMO_MARKER, organization, "Explicit fictional demonstration seeded into a previously empty database. No certificate was granted.")
