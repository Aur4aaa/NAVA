"""Shared module registry: labels and public routes, never an authorization boundary."""
from dataclasses import dataclass
from django.apps import apps


@dataclass(frozen=True)
class Module:
    model_name: str
    title: str
    singular: str
    description: str
    icon: str
    section: str = 'WORKSPACE'

    @property
    def model(self):
        return apps.get_model('workspace', self.model_name)


MODULES = {
    'scopes': Module('ScopeVersion', 'Context & scope', 'scope version', 'Define your boundaries, context, and climate relevance. Approved scope versions retain their history.', 'layers'),
    'requirements': Module('Requirement', 'Requirements', 'requirement', 'Keep obligations and their sources connected to the controls that address them.', 'file'),
    'parties': Module('InterestedParty', 'Interested parties', 'interested party', 'Record relevant parties and their information security requirements.', 'users'),
    'gaps': Module('GapAssessment', 'Gap assessment', 'assessment', 'Assess management requirements and controls independently. An upload alone does not demonstrate effectiveness.', 'clipboard'),
    'risks': Module('RiskAssessmentVersion', 'Risk register', 'risk assessment', 'Understand the scenarios that matter. Preserve your methodology, rationale, and treatment decisions.', 'shield'),
    'methodologies': Module('RiskMethodologyVersion', 'Risk methodology', 'methodology', 'Versioned assessment scales and acceptance criteria. The default 5 × 5 matrix is an internal planning method.', 'grid'),
    'treatments': Module('TreatmentPlan', 'Risk treatment', 'treatment plan', 'Translate risk decisions into owned actions and selected controls. Risk scores require an explicit assessment.', 'git-branch'),
    'acceptances': Module('RiskAcceptance', 'Risk acceptance', 'risk acceptance', 'Record authorized residual risk decisions, justification, and expiry.', 'check-circle'),
    'controls': Module('ControlImplementation', 'Controls & SoA', 'control implementation', 'Keep applicability, implementation, evidence, and effectiveness separate.', 'check-square'),
    'soa': Module('SoAVersion', 'SoA versions', 'SoA version', 'Freeze a reviewed statement of applicability with inclusion and exclusion justifications.', 'layers'),
    'documents': Module('DocumentVersion', 'Documents', 'document version', 'Review and publish controlled documents. Revisions preserve the previously approved content.', 'file-text'),
    'evidence': Module('EvidenceVersion', 'Evidence library', 'evidence version', 'Private evidence with file checksums, review history, classification, and expiry dates.', 'folder'),
    'tasks': Module('Task', 'Action center', 'task', 'Focus on blockers, overdue reviews, and the work that moves your ISMS forward.', 'check-circle'),
    'audits': Module('Audit', 'Audit workspace', 'audit', 'Plan internal audits and track Stage 1 and Stage 2 independently from certification decisions.', 'clipboard', 'ASSURANCE'),
    'findings': Module('Finding', 'Audit findings', 'finding', 'Record objective evidence, requirements, and nonconformities that need action.', 'alert-circle', 'ASSURANCE'),
    'actions': Module('CorrectiveAction', 'Corrective actions', 'corrective action', 'Connect root cause, correction, implementation evidence, and independent effectiveness checks.', 'git-branch', 'ASSURANCE'),
    'reviews': Module('ManagementReview', 'Management reviews', 'management review', 'Record decisions, owners, and minutes alongside a frozen snapshot of the records reviewed.', 'users', 'ASSURANCE'),
    'certifications': Module('CertificationRecord', 'Certification tracker', 'certification record', 'Record the certification body’s documented decision. Internal readiness is not a certification decision.', 'award', 'ASSURANCE'),
    'packs': Module('AuditPack', 'Audit packages', 'audit package', 'Freeze permission-filtered versions and download a traceability manifest with evidence.', 'archive', 'ASSURANCE'),
}


def module_for_record(record):
    return next((kind for kind, module in MODULES.items() if module.model_name == record.__class__.__name__), None)


def record_url(record):
    kind = module_for_record(record)
    return f'/records/{kind}/{record.pk}/' if kind else ''


def label_status(value):
    return str(value or 'draft').replace('_', ' ').capitalize()
